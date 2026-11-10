# Yarilo

[Русский](README.ru.md)

Brightness of your external monitors from the Windows tray: a slider instead of the buttons on the
monitor. Optional: auto brightness from a light sensor, with day and night curves that follow the sun.

Yarilo talks to the monitor itself over DDC/CI, the data channel inside the video cable. So it is the
monitor's own brightness setting that changes, not a dimmed picture.

## What it does

- **Slider.** Left click on the sun in the tray: one slider for all monitors, or one per monitor
  (untick "Together").
- **Brighter / Darker** in the menu, and hotkeys if you want them (off by default).
- **Auto brightness, with a light sensor.** Any HTTP address that answers JSON with a number works,
  for example the ESPHome firmware in [`firmware/`](firmware/). You also get a light log and a chart.
- **Day and night curves, with your location.** The same 8 lux wants a brighter screen at noon than
  under a lamp at night. Yarilo mixes the two curves by the height of the sun, smoothly through twilight.

## What you need

- Windows 10 or 11.
- Monitors with DDC/CI. Most desktop monitors have it; it can be switched off in the monitor's own
  menu. Laptop panels do not use DDC/CI and are not controlled.
- 64-bit Python 3.10 or newer. `yarilo.cmd` finds it or tells you what to install.

## Install and run

1. Download the code: `git clone https://github.com/bsdate-cc/yarilo`, or Code → Download ZIP.
2. Double-click `yarilo.cmd`. The first start makes `.venv` and installs the libraries
   (pystray, Pillow, astral).
3. A sun appears in the tray. Left click opens the sliders, right click opens the menu. "Start with
   Windows" is in the menu.

## Does my monitor work?

Run `probe.cmd`, or `.venv\Scripts\python -m yarilo probe`. For each monitor, left to right, it prints:
- whether it answers;
- its brightness and maximum;
- whether writing the same value back works;
- the VCP codes the monitor lists about itself.

If a monitor does not answer:
- switch DDC/CI on in its menu;
- try a direct cable. Docks, KVM switches and some USB-C/HDMI adapters do not pass DDC/CI.

For anything stranger, give your coding agent [`docs/for-agents.md`](docs/for-agents.md) together
with the output of `probe --json`.

## Settings

The settings file is `%USERPROFILE%\.yarilo\config.json`. Open it from the menu → "Open settings";
Yarilo picks up changes while it runs. Monitors are numbered left to right from 1. Missing keys get
the defaults from [`yarilo/config.py`](yarilo/config.py).

| Key | Default | What it does |
|---|---|---|
| `language` | `"auto"` | `"ru"` or `"en"`; auto follows Windows |
| `linked` | `true` | one slider for all monitors |
| `monitor_offsets` | `[]` | added to the common brightness, left to right, e.g. `[5, 0]` when the left one looks darker |
| `skip_monitors` | `[]` | numbers of monitors Yarilo never touches, e.g. `[3]` |
| `vcp_code` | `16` | 0x10, brightness in the DDC/CI standard |
| `step` | `5` | for Brighter/Darker and the hotkeys |
| `min`, `max` | `0`, `100` | limits, in percent |
| `hotkeys` | `{"brighter": "", "darker": ""}` | e.g. `"ctrl+alt+up"`, `"ctrl+alt+down"` |
| `sensor_urls` | `[]` | light sensor addresses; one turns auto brightness on |
| `sensor_json_field` | `"value"` | the JSON field with the lux number |
| `location` | `null` | `{"name": "Moscow", "lat": 55.75, "lon": 37.62}` turns on the night curve |
| `points_day`, `points_night` | see config.py | `[lux, brightness]` points |
| `smooth` | `true` | auto changes go one unit at a time; `false` jumps in one write |

## Auto brightness

How it decides:
- **Ignores short changes.** It takes the median light over 20 seconds, so a hand or a shadow
  changes nothing.
- **Changes rarely.** Only when the target differs by at least 4 for 30 seconds. A jump of 15 or more,
  such as a room light switched on, needs only 5 seconds.
- **Lets you take over.** The slider or Brighter/Darker turns auto brightness off; tick "Auto
  brightness" to bring it back. If you change brightness with the monitor's own buttons, Yarilo
  leaves it alone for an hour.

A monitor may save each change in its own memory. That is why Yarilo changes rarely and has the
`smooth` setting.

The sensor in [`firmware/`](firmware/) is an ESP32-C3 Super Mini with a GY-302 (BH1750) on ESPHome;
the wiring and flashing are described there. A printable wall case for it is in
[`hardware/case/`](hardware/case/). The light log is in `%USERPROFILE%\.yarilo\lux\`. Menu →
"Light chart" opens a page with every day, sunrise and sunset; the page itself is in Russian for now.

## Files

All in `%USERPROFILE%\.yarilo\`:
- `config.json` — the settings;
- `yarilo.log` — the log;
- `lux\` — the light log, with a sensor;
- `lux.html` — the chart.

## Development

    .venv\Scripts\python -m pip install -r requirements-dev.txt
    .venv\Scripts\python -m pytest -q

## License

MIT, see [LICENSE](LICENSE).
