"""Settings file: %USERPROFILE%\\.yarilo\\config.json. Missing keys come from DEFAULTS.

Monitors are numbered left to right from 1, as they stand on the desktop.
"""
import copy
import json
import os
from pathlib import Path

HOME = Path(os.environ.get("USERPROFILE", Path.home()))
DATA_DIR = HOME / ".yarilo"
CONFIG_PATH = DATA_DIR / "config.json"

DEFAULTS = {
    "language": "auto",              # auto (as Windows), ru, en

    # --- monitors ---
    "linked": True,                  # one slider for all monitors; false - one per monitor
    "monitor_offsets": [],           # added to the common brightness, left to right: [5, 0]
    "skip_monitors": [],             # numbers of monitors never to touch: [3]
    "vcp_code": 16,                  # 0x10 = brightness in the DDC/CI standard (MCCS)
    "step": 5,                       # "brighter/darker" and hotkeys
    "min": 0,
    "max": 100,
    "hotkeys": {"brighter": "", "darker": ""},   # e.g. "ctrl+alt+up"; empty = off

    # --- light sensor (optional): any HTTP address answering JSON with a number ---
    "sensor_urls": [],               # e.g. ["http://lux-sensor.local/sensor/Illuminance"]
    "sensor_json_field": "value",
    "poll_s": 2,
    "window_s": 20,                  # median over this long: a finger or a shadow is ignored
    "stale_s": 30,                   # no answer this long -> the sensor is down
    "threshold": 4,                  # change only when the target differs this much...
    "hold_s": 30,                    # ...for this long
    "fast_jump": 15,                 # a bigger difference (room light on)...
    "fast_hold_s": 5,                # ...waits only this long
    "manual_pause_min": 60,          # brightness changed with the monitor buttons -> wait
    "smooth": True,                  # change by 1 at a time (more writes to the monitor)
    "smooth_step_s": 0.15,
    "record_light": True,            # light log for the chart (only with a sensor)

    # --- the sun (optional): day and night curves ---
    "location": None,                # {"name": "Moscow", "lat": 55.75, "lon": 37.62}
    # (lux, brightness) by day and by night; in twilight the two are mixed; without a
    # location only the day curve is used
    "points_day": [[1, 30], [30, 55], [300, 90]],
    "points_night": [[3, 0], [8, 10], [30, 40], [300, 90]],
    "night_below_deg": -6,           # sun lower - night curve only
    "day_above_deg": 3,              # sun higher - day curve only
}




def load(path: Path = CONFIG_PATH) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    path = Path(path)
    if not path.exists():
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except (ValueError, OSError):
        os.replace(path, path.with_name(path.name + ".bad"))
        return cfg
    cfg.update(data)
    return cfg


def save(path: Path, cfg: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
