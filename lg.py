import asyncio
import threading

from aiohttp import ClientSession
from thinqconnect.thinq_api import ThinQApi

from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver


# =========================================================
# CONFIG
# =========================================================

from config import load_config

settings = load_config()
ACCESS_TOKEN = settings["ACCESS_TOKEN"]
COUNTRY_CODE = settings["COUNTRY_CODE"]
CLIENT_ID = settings["CLIENT_ID"]
POLL_INTERVAL = settings["POLL_INTERVAL"]
HOMEKIT_PORT = settings["HOMEKIT_PORT"]
PERSIST_FILE = settings["PERSIST_FILE"]


# =========================================================
# LG STATUS
# =========================================================

STATE_NAMES = {
    "INITIAL": "Bereit",
    "POWER_OFF": "Aus",
    "RESERVED": "Geplant",
    "DETECTING": "Beladung erkennen",
    "RUNNING": "Läuft",
    "WASHING": "Waschen",
    "RINSING": "Spülen",
    "SPINNING": "Schleudern",
    "DRYING": "Trocknen",
    "PAUSE": "Pausiert",
    "COMPLETE": "Fertig",
    "END": "Fertig",
}


RUNNING_STATES = {
    "RESERVED",
    "DETECTING",
    "RUNNING",
    "WASHING",
    "RINSING",
    "SPINNING",
    "DRYING",
    "PAUSE",
}


FINISHED_STATES = {
    "COMPLETE",
    "END",
}


# =========================================================
# GEMEINSAMER STATUS
# =========================================================

class WasherState:
    def __init__(self):
        self.raw_state = "UNKNOWN"

        self.remain_hour = 0
        self.remain_minute = 0

        self.total_hour = 0
        self.total_minute = 0

        self.remote_control = False
        self.cycle_count = 0

        self.alias = "Waschmaschine"
        self.model = "Unbekannt"


washer_state = WasherState()


# =========================================================
# LG THINQ CLIENT
# =========================================================

class LGWasherClient:
    def __init__(self):
        self.device_id = None

    async def find_washer(self, api):
        devices = await api.async_get_device_list()

        for device in devices:
            info = device.get("deviceInfo", {})

            if info.get("deviceType") == "DEVICE_WASHER":
                self.device_id = device["deviceId"]

                washer_state.alias = info.get(
                    "alias",
                    "Waschmaschine"
                )

                washer_state.model = info.get(
                    "modelName",
                    "Unbekannt"
                )

                print()
                print("===================================")
                print("LG Waschmaschine gefunden")
                print("===================================")
                print(f"Name:   {washer_state.alias}")
                print(f"Modell: {washer_state.model}")
                print("===================================")
                print()

                return True

        return False

    async def update_status(self, api):
        result = await api.async_get_device_status(
            self.device_id
        )

        if not result:
            raise RuntimeError(
                "Keine Statusdaten erhalten."
            )

        status = result[0]

        # Zustand
        washer_state.raw_state = (
            status
            .get("runState", {})
            .get("currentState", "UNKNOWN")
        )

        # Timer
        timer = status.get("timer", {})

        washer_state.remain_hour = timer.get(
            "remainHour",
            0
        )

        washer_state.remain_minute = timer.get(
            "remainMinute",
            0
        )

        washer_state.total_hour = timer.get(
            "totalHour",
            0
        )

        washer_state.total_minute = timer.get(
            "totalMinute",
            0
        )

        # Remote Control
        washer_state.remote_control = (
            status
            .get("remoteControlEnable", {})
            .get("remoteControlEnabled", False)
        )

        # Waschzyklen
        washer_state.cycle_count = (
            status
            .get("cycle", {})
            .get("cycleCount", 0)
        )

    async def run(self, accessory):
        async with ClientSession() as session:
            api = ThinQApi(
                session=session,
                access_token=ACCESS_TOKEN,
                country_code=COUNTRY_CODE,
                client_id=CLIENT_ID
            )

            # ---------------------------------------------
            # Waschmaschine finden
            # ---------------------------------------------

            while self.device_id is None:
                try:
                    found = await self.find_washer(api)

                    if found:
                        break

                    print(
                        "Keine Waschmaschine gefunden. "
                        "Neuer Versuch in 30 Sekunden..."
                    )

                except Exception as e:
                    print(
                        f"Fehler bei Gerätesuche: {type(e).__name__}"
                    )

                await asyncio.sleep(30)

            print("Statusüberwachung gestartet.")
            print()

            # ---------------------------------------------
            # Status überwachen
            # ---------------------------------------------

            while True:
                try:
                    await self.update_status(api)

                    accessory.update_homekit()

                    self.print_status()

                except Exception as e:
                    print()
                    print(f"ThinQ Fehler: {type(e).__name__}")
                    print(
                        f"Neuer Versuch in "
                        f"{POLL_INTERVAL} Sekunden..."
                    )

                await asyncio.sleep(POLL_INTERVAL)

    def print_status(self):
        state = washer_state.raw_state

        readable_state = STATE_NAMES.get(
            state,
            state
        )

        running = state in RUNNING_STATES

        remaining_minutes = (
            washer_state.remain_hour * 60
            + washer_state.remain_minute
        )

        total_minutes = (
            washer_state.total_hour * 60
            + washer_state.total_minute
        )

        print("---------")
        print(f"Status:         {readable_state}")

        print(
            f"Läuft:          "
            f"{'Ja' if running else 'Nein'}"
        )

        print(
            f"Restzeit:       "
            f"{washer_state.remain_hour}h "
            f"{washer_state.remain_minute:02d}min "
            f"({remaining_minutes} min)"
        )

        print(
            f"Gesamtdauer:    "
            f"{washer_state.total_hour}h "
            f"{washer_state.total_minute:02d}min "
            f"({total_minutes} min)"
        )

        print(
            f"Remote Control: "
            f"{'Ja' if washer_state.remote_control else 'Nein'}"
        )

        print(
            f"Waschzyklen:    "
            f"{washer_state.cycle_count}"
        )


# =========================================================
# HOMEKIT
# =========================================================

class LGWasherAccessory(Accessory):

    # Valve/Faucet-artige Kategorie,
    # damit RemainingDuration von Apple Home dargestellt wird.
    category = 28

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.previous_running = None

        # -------------------------------------------------
        # Geräteinformationen
        # -------------------------------------------------

        self.set_info_service(
            manufacturer="LG Electronics",
            model="LG ThinQ Washer",
            serial_number="LG-THINQ-WASHER",
            firmware_revision="1.3"
        )

        # =================================================
        # HAUPTSERVICE
        # =================================================

        self.valve_service = self.add_preload_service(
            "Valve",
            chars=[
                "RemainingDuration",
                "SetDuration"
            ]
        )

        self.set_primary_service(
            self.valve_service
        )

        self.active_char = (
            self.valve_service.configure_char(
                "Active",
                setter_callback=self.set_active
            )
        )

        self.in_use_char = (
            self.valve_service.configure_char(
                "InUse"
            )
        )

        self.remaining_duration_char = (
            self.valve_service.configure_char(
                "RemainingDuration"
            )
        )

        self.set_duration_char = (
            self.valve_service.configure_char(
                "SetDuration"
            )
        )

        self.valve_type_char = (
            self.valve_service.configure_char(
                "ValveType"
            )
        )

        self.valve_type_char.set_value(0)

        self.active_char.set_value(0)
        self.in_use_char.set_value(0)
        self.remaining_duration_char.set_value(0)
        self.set_duration_char.set_value(0)

        # =================================================
        # THINQ STARTEN
        # =================================================

        self.client = LGWasherClient()

        threading.Thread(
            target=self.start_thinq,
            daemon=True
        ).start()

    # =====================================================
    # THINQ THREAD
    # =====================================================

    def start_thinq(self):
        asyncio.run(
            self.client.run(self)
        )

    # =====================================================
    # HOMEKIT UPDATE
    # =====================================================

    def update_homekit(self):
        state = washer_state.raw_state

        running = state in RUNNING_STATES
        finished = state in FINISHED_STATES

        remaining_seconds = (
            washer_state.remain_hour * 3600
            + washer_state.remain_minute * 60
        )

        total_seconds = (
            washer_state.total_hour * 3600
            + washer_state.total_minute * 60
        )

        # -------------------------------------------------
        # Hauptgerät
        # -------------------------------------------------

        self.active_char.set_value(
            1 if running else 0
        )

        self.in_use_char.set_value(
            1 if running else 0
        )

        # -------------------------------------------------
        # Restzeit
        # -------------------------------------------------

        if running:
            self.remaining_duration_char.set_value(
                remaining_seconds
            )

            self.set_duration_char.set_value(
                total_seconds
            )

        else:
            self.remaining_duration_char.set_value(0)

        # -------------------------------------------------
        # Zustandswechsel loggen
        # -------------------------------------------------

        if (
            running
            and self.previous_running is False
        ):
            print()
            print("===================================")
            print("▶ WASCHGANG GESTARTET")
            print("Contact Sensor -> CLOSED")
            print("===================================")
            print()

        if (
            finished
            and self.previous_running is True
        ):
            print()
            print("===================================")
            print("✅ WASCHGANG FERTIG")
            print("Contact Sensor -> OPEN")
            print("===================================")
            print()

        self.previous_running = running

    # =====================================================
    # HOMEKIT NICHT STEUERN LASSEN
    # =====================================================

    def set_active(self, value):
        print(
            f"HomeKit-Schaltbefehl ignoriert: {value}"
        )

        self.update_homekit()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    driver = AccessoryDriver(
        port=HOMEKIT_PORT,
        persist_file=PERSIST_FILE
    )

    accessory = LGWasherAccessory(
        driver,
        "Waschmaschine"
    )

    driver.add_accessory(
        accessory=accessory
    )

    driver.start()
