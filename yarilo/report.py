"""Light chart: reads the light log, adds sunrise/sunset, writes one HTML page.

    python -m yarilo.report      # build and open
"""
import csv
import json
import webbrowser
from datetime import date, datetime
from pathlib import Path
from statistics import median

from . import config

TEMPLATE = Path(__file__).with_name("report_template.html")
OUT = config.DATA_DIR / "lux.html"
_WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
_MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def _vals(text: str):
    return [int(v) for v in text.split("/")] if text else None


def _lux(text: str):
    return float(text) if text else None


def read_samples(path: Path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [(datetime.fromisoformat(r["time"]), _lux(r["lux"]), _vals(r["monitors"]), r["mode"])
                for r in csv.DictReader(f)]


def read_events(path: Path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [{"time": datetime.fromisoformat(r["time"]), "kind": r["kind"], "lux": _lux(r["lux"]),
                 "before": _vals(r["before"]), "after": _vals(r["after"])}
                for r in csv.DictReader(f)]


def per_minute(rows: list) -> list:
    """[minute of day, median lux, min, max, brightness per monitor, mode] for every minute with data."""
    groups: dict[int, list] = {}
    for when, lux, vals, mode in rows:
        groups.setdefault(when.hour * 60 + when.minute, []).append((lux, vals, mode))
    out = []
    for m in sorted(groups):
        g = groups[m]
        lux = [x for x, _, _ in g if x is not None]
        vals = next((v for _, v, _ in reversed(g) if v), None)
        out.append([m,
                    median(lux) if lux else None,
                    min(lux) if lux else None,
                    max(lux) if lux else None,
                    vals, g[-1][2]])
    return out


def sun_minutes(day: date, lat: float, lon: float) -> dict:
    from astral import Observer
    from astral.sun import sun
    tz = datetime.now().astimezone().tzinfo
    s = sun(Observer(lat, lon), date=day, tzinfo=tz)
    return {k: s[k].hour * 60 + s[k].minute + s[k].second / 60
            for k in ("dawn", "sunrise", "noon", "sunset", "dusk")}


def summarize(day: date, minutes: list, events: list, sun: dict, threshold: float = 10) -> dict:
    lit = [(m, med) for m, med, *_ in minutes if med is not None]
    peak = max(lit, key=lambda p: p[1], default=(None, None))
    dark_from = None
    after_noon = [(m, med) for m, med in lit if m >= sun["noon"]]
    for i in range(len(after_noon) - 9):
        if all(med < threshold for _, med in after_noon[i:i + 10]):
            dark_from = after_noon[i][0]
            break
    near_sunset = [med for m, med in lit if abs(m - sun["sunset"]) <= 5]
    today = [e for e in events if e["time"].date() == day]
    writes = sum(max(abs(a - b) for a, b in zip(e["after"], e["before"]))
                 for e in today if e["kind"] in ("auto", "hand") and e["before"] and e["after"])
    return {
        "hours": round(len(minutes) / 60, 1),
        "peak_lux": peak[1], "peak_at": peak[0],
        "dark_from": dark_from,
        "at_sunset": median(near_sunset) if near_sunset else None,
        "auto": sum(e["kind"] == "auto" for e in today),
        "hand": sum(e["kind"] == "hand" for e in today),
        "joystick": sum(e["kind"] == "joystick" for e in today),
        "writes": writes,
    }


def _label(day: date) -> str:
    return f"{_WEEKDAYS[day.weekday()]} {day.day} {_MONTHS[day.month - 1]}"


def collect(data_dir: Path, location: dict | None, days: int = 14) -> dict:
    data_dir = Path(data_dir)
    events = read_events(data_dir / "events.csv")
    files = sorted(data_dir.glob("lux-????-??-??.csv"))[-days:]
    out = []
    for f in files:
        day = date.fromisoformat(f.stem[4:])
        mins = per_minute(read_samples(f))
        if not mins:
            continue
        sun = sun_minutes(day, location["lat"], location["lon"]) if location else None
        ev = [[e["time"].hour * 60 + e["time"].minute + e["time"].second / 60, e["kind"], e["lux"],
               e["before"], e["after"]] for e in events if e["time"].date() == day]
        out.append({"date": day.isoformat(), "label": _label(day), "sun": sun,
                    "pts": [[m, med, lo, hi, (v or [None])[0], (v or [None])[-1], mode]
                            for m, med, lo, hi, v, mode in mins],
                    "ev": ev, "sum": summarize(day, mins, events, sun or {"noon": 720, "sunset": -999})})
    return {"location": (location or {}).get("name", ""), "folder": str(data_dir),
            "generated": datetime.now().strftime("%d.%m.%Y %H:%M"), "days": out}


def build(data_dir: Path = config.DATA_DIR / "lux", out: Path = OUT, cfg: dict | None = None) -> Path:
    cfg = cfg or config.load()
    data = collect(data_dir, cfg["location"])
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/null", payload)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def build_and_open(cfg: dict | None = None) -> Path:
    path = build(cfg=cfg)
    webbrowser.open(path.as_uri())
    return path


if __name__ == "__main__":
    print(build_and_open())
