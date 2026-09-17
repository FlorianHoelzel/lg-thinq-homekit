# LG ThinQ HomeKit

Expose an LG ThinQ washing machine's running state and remaining time to
Apple Home using HAP-python. The accessory uses a Valve service to display
duration; HomeKit control commands are ignored. The first washer returned
by ThinQ is selected. Console status messages are in German.

## Features

- Show whether a wash cycle is active in Apple Home.
- Report remaining cycle time through the HomeKit Valve service.
- Print the current phase, remaining time, remote-control availability and cycle count.
- Retry ThinQ discovery and polling when requests fail.
- Preserve HomeKit identity and pairings across restarts.

This is a status-only integration: it does not start, pause or stop the washer.
It currently supports one washer and does not offer a device selector.

## Setup

Use a Python installation compatible with the pinned dependencies, a ThinQ
account with a washing machine, and a host on your HomeKit network with internet
access to ThinQ. The commands below are for Linux and macOS.

Clone the repository and enter its directory before continuing:

```sh
git clone https://github.com/FlorianHoelzel/lg-thinq-homekit.git
cd lg-thinq-homekit
```

Access to the private repository requires GitHub authentication.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp config.example.json config.local.json
chmod 600 config.local.json
```

Fill in `ACCESS_TOKEN` with your ThinQ API token and `CLIENT_ID` with your
ThinQ client identifier in `config.local.json`. Set `COUNTRY_CODE` for your
account (default: `DE`). Do not put credentials into Python source files.

```sh
.venv/bin/python lg.py
```

Pair the accessory using the HomeKit pairing information displayed at startup.
Keep the process running on a machine accessible to your HomeKit devices.
The default HomeKit port is 51827 and the polling interval is 15 seconds.

## Configuration

| Key | Purpose | Default |
| --- | --- | --- |
| `ACCESS_TOKEN` | ThinQ API access token | Required |
| `CLIENT_ID` | ThinQ API client identifier | Required |
| `COUNTRY_CODE` | ThinQ account country | `DE` |
| `POLL_INTERVAL` | Seconds between status requests | `15` |
| `HOMEKIT_PORT` | HomeKit listener port | `51827` |
| `PERSIST_FILE` | Local HomeKit identity and pairing state | `accessory.state` |

Every configuration key supports an environment override prefixed with `LG_`,
such as `LG_ACCESS_TOKEN` or `LG_HOMEKIT_PORT`. A local config file is optional
when required credentials are supplied through the environment. `.env` files
are not loaded automatically. Relative state paths resolve against this project
directory, independent of the working directory used to start the script.

## Troubleshooting

- **Missing configuration:** fill in the required fields in `config.local.json`
  or provide their environment overrides. The example intentionally leaves them empty.
- **No washer found:** check that the token, client identifier and country belong
  to the account containing the washer. Discovery retries every 30 seconds.
- **ThinQ errors:** check internet access and credential validity. Error output
  includes the exception type without printing raw API errors that could expose credentials.
- **HomeKit cannot discover the accessory:** ensure the host and HomeKit devices
  can communicate locally, including Bonjour/mDNS, and allow the configured port.
- **Pairing after a restart:** keep the existing state file. Removing it loses
  the saved HomeKit identity and pairings.

## Publishing safely

`config.example.json` deliberately contains no credentials. Git ignores
`config.local.json`, legacy `tokens.py`, `.env` files, HomeKit `*.state` files,
the local virtual environment and the unused `wideq` checkout.
HomeKit state contains private pairing material; preserve it locally to retain
existing pairings. If you customize `PERSIST_FILE`, keep it outside the repository
or use a `.state` filename covered by the ignore rules.

Before committing, inspect `git status --short` and `git diff --cached`.
Never force-add ignored private files. Share a Git checkout or `git archive`,
not a zip of this working folder, which still contains local credentials.
If a token has previously been shared or committed elsewhere, revoke it and
replace it; ignore rules cannot remove credentials from existing Git history.

The dependency versions in `requirements.txt` match the original local environment.
