"""Load private local settings, with environment variables taking precedence."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_config():
    path = ROOT / "config.local.json"
    try:
        settings = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        raise SystemExit("Cannot read config.local.json; check its permissions and JSON syntax.") from None
    if not isinstance(settings, dict):
        raise SystemExit("config.local.json must contain a JSON object.")

    defaults = {
        "ACCESS_TOKEN": "",
        "CLIENT_ID": "",
        "COUNTRY_CODE": "DE",
        "POLL_INTERVAL": 15,
        "HOMEKIT_PORT": 51827,
        "PERSIST_FILE": str(ROOT / "accessory.state"),
    }
    for key, default in defaults.items():
        settings[key] = os.environ.get("LG_" + key, settings.get(key, default))
    for key in ("ACCESS_TOKEN", "CLIENT_ID", "COUNTRY_CODE", "PERSIST_FILE"):
        if not isinstance(settings[key], str) or not settings[key].strip():
            raise SystemExit(f"Set {key} in config.local.json or LG_{key} in the environment.")
    for key, maximum in (("POLL_INTERVAL", None), ("HOMEKIT_PORT", 65535)):
        try:
            value = settings[key]
            if isinstance(value, bool) or not str(value).isdigit():
                raise ValueError
            settings[key] = int(value)
            if settings[key] < 1 or (maximum and settings[key] > maximum):
                raise ValueError
        except (TypeError, ValueError):
            raise SystemExit(f"{key} must be a positive integer" + (f" no greater than {maximum}." if maximum else ".")) from None
    persist = Path(settings["PERSIST_FILE"]).expanduser()
    settings["PERSIST_FILE"] = str(persist if persist.is_absolute() else ROOT / persist)
    return settings
