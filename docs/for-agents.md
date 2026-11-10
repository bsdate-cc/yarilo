# Yarilo on an unfamiliar monitor: notes for a coding agent

Your user wants Yarilo to control the brightness of their monitors and something does not work.
These notes say how to find out what the monitor does and where to change Yarilo. Every value
written over DDC/CI changes the user's monitor right away: say what you are going to write, and
ask the user what they saw.

## 1. Look before touching anything

    .venv\Scripts\python -m yarilo probe --json

For every monitor, left to right, it reports:

| Field | Meaning |
|---|---|
| `answers` | the monitor replied to a DDC/CI read of `vcp_code` |
| `current`, `maximum` | raw values; Yarilo scales to percent when the maximum is not 100 |
| `write` | the same value written back: `ok`, `ms`, `read_back` |
| `read_ms` | how long one read took |
| `capabilities` | the raw capabilities string |
| `vcp_codes` | the codes parsed from the capabilities string |
| `lists_brightness_0x10` | whether 0x10 is among those codes |
| `skipped_in_settings` | the monitor is in `skip_monitors` |

The probe ignores `skip_monitors`, so a skipped monitor is still reported. `--no-caps` skips the slow
capabilities request, and `--monitor N` checks one monitor only.

## 2. Reading the result

| What you see | Likely reason | What to do |
|---|---|---|
| `answers: false` on every monitor | DDC/CI is off in the monitor menus; or a dock, KVM or adapter is in between; or the GPU driver blocks it (some virtual machines, DisplayLink) | ask the user to enable DDC/CI in the monitor's OSD and to try a direct cable |
| `answers: false` on one monitor | that monitor or its cable path; laptop panels always say no | add its number to `skip_monitors` so Yarilo leaves it alone |
| `write.ok: true` but `read_back` differs | the monitor applies slowly or rounds | write, wait 0.5–1 s and read again; raise `smooth_step_s` if smooth changes stutter |
| `maximum` is not 100 | normal for some models | nothing to do: `ddc.py` scales |
| `lists_brightness_0x10: false` | the monitor lists something else, or its capabilities string is incomplete | first try 0x10 anyway: `probe --monitor N --set 40`; if nothing changes, look for a backlight code in `vcp_codes` (0x6B is a common one) and try `probe --monitor N --vcp 0x6B --set 40` |
| `read_ms` above ~300 | slow DDC/CI | everything is synchronous and just slower; keep `smooth` false so a change is one write |
| monitors in a different order than on the desk | Yarilo orders by the desktop position (Windows display settings) | match the order in Windows, or use the numbers the probe prints |

## 3. Codes never to write while experimenting

A VCP code is a command, not only a value. These change much more than brightness:

| Code | What it does |
|---|---|
| 0x04 | factory reset |
| 0x05 | brightness/contrast reset |
| 0x08 | colour reset |
| 0x60 | input source — the screen goes black on another input |
| 0xD6 | power mode — the monitor turns off |
| 0xDC | display mode |

Write only the code you are testing, with a percent the user agreed to. 0x12 is contrast: it is safe,
but it is not brightness.

## 4. Settings

The settings live in `%USERPROFILE%\.yarilo\config.json`; the defaults and comments are `DEFAULTS` in
`yarilo/config.py`. Yarilo re-reads the file while running. The usual changes:

| Key | When to set it |
|---|---|
| `vcp_code` | the brightness code, if the monitor needs something other than 0x10 |
| `skip_monitors` | monitor numbers (left to right from 1) to leave alone |
| `monitor_offsets` | per-monitor offsets for the linked slider |
| `min`, `max` | for a monitor that goes black at 0, or is too bright at 100 |
| `smooth`, `smooth_step_s` | how auto brightness steps |

## 5. Where things are in the code

| File | What it does |
|---|---|
| `yarilo/ddc.py` | every DDC/CI call (dxva2): enumeration left to right, get/set with one retry, percent scaling, capabilities. A monitor-specific quirk such as a delay after a write, a different code or an extra retry belongs here. |
| `yarilo/app.py` | the tray. `_apply_values` is the one write path: it reads the monitors, notices changes made with the monitor buttons, writes (smoothly or at once) and records what is on the monitors. |
| `yarilo/popup.py` | the slider window (tkinter). |
| `yarilo/controller.py` | auto brightness logic, pure functions with no I/O: median, dead band, hold times, curves. |
| `yarilo/sensor.py` | the light sensor over HTTP. For Home Assistant or another source, change `http_fetch` (for example add an `Authorization` header) and keep `parse`. |
| `yarilo/sun.py` | sun height and the day/night weight. |
| `yarilo/probe.py` | the check above. |

## 6. Tests

    .venv\Scripts\python -m pip install -r requirements-dev.txt
    .venv\Scripts\python -m pytest -q

`tests/test_app_modes.py` shows how to run the app against fake monitors. Use the same pattern to
reproduce a quirk before changing `ddc.py` or `app.py`.
