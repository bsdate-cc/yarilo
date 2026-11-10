from datetime import date, datetime

from yarilo.recorder import Recorder
from yarilo.report import per_minute, read_events, read_samples, summarize


def test_read_samples_back(tmp_path):
    r = Recorder(tmp_path)
    r.sample(datetime(2026, 11, 9, 14, 0, 2), 13.7, [50, 45], "auto")
    r.sample(datetime(2026, 11, 9, 14, 0, 4), None, None, "off")
    rows = read_samples(tmp_path / "lux-2026-11-09.csv")
    assert rows == [
        (datetime(2026, 11, 9, 14, 0, 2), 13.7, [50, 45], "auto"),
        (datetime(2026, 11, 9, 14, 0, 4), None, None, "off"),
    ]


def test_read_events_back(tmp_path):
    r = Recorder(tmp_path)
    r.event(datetime(2026, 11, 9, 14, 1, 0), "hand", 13.7, [50, 45], [55, 50])
    assert read_events(tmp_path / "events.csv") == [
        {"time": datetime(2026, 11, 9, 14, 1, 0), "kind": "hand", "lux": 13.7,
         "before": [50, 45], "after": [55, 50]},
    ]


def test_read_missing_files(tmp_path):
    assert read_samples(tmp_path / "lux-2026-11-09.csv") == []
    assert read_events(tmp_path / "events.csv") == []


def s(h, m, sec, lux, vals=(50, 45), mode="auto"):
    return (datetime(2026, 11, 9, h, m, sec), lux, list(vals) if vals else None, mode)


def test_per_minute_median_min_max():
    rows = [s(14, 0, 0, 10), s(14, 0, 2, 30), s(14, 0, 4, 20), s(14, 1, 0, 5, (40, 35), "hold")]
    assert per_minute(rows) == [
        [840, 20, 10, 30, [50, 45], "auto"],
        [841, 5, 5, 5, [40, 35], "hold"],
    ]


def test_per_minute_without_light():
    rows = [s(14, 0, 0, None), s(14, 0, 2, None, None)]
    assert per_minute(rows) == [[840, None, None, None, [50, 45], "auto"]]


def minutes_from(spec):
    """spec: list of (minute, lux)."""
    return [[m, lux, lux, lux, [50, 45], "auto"] for m, lux in spec]


def test_summary_peak_and_dark_from():
    mins = minutes_from([(600, 50), (720, 300), (721, 280), (960, 40)]
                        + [(1000 + i, 8) for i in range(10)]   # dark from 16:40
                        + [(1100, 30)])
    sun = {"dawn": 434, "sunrise": 472, "noon": 743, "sunset": 1013, "dusk": 1051}
    out = summarize(date(2026, 11, 9), mins, [], sun, threshold=10)
    assert out["peak_lux"] == 300
    assert out["peak_at"] == 720
    assert out["dark_from"] == 1000
    assert out["at_sunset"] == 8
    assert out["hours"] == round(len(mins) / 60, 1)


def test_summary_short_dip_is_not_dark():
    mins = minutes_from([(800 + i, 5) for i in range(3)] + [(803 + i, 50) for i in range(20)])
    sun = {"dawn": 434, "sunrise": 472, "noon": 743, "sunset": 1013, "dusk": 1051}
    out = summarize(date(2026, 11, 9), mins, [], sun, threshold=10)
    assert out["dark_from"] is None
    assert out["at_sunset"] is None


def test_summary_counts_changes_and_writes():
    ev = [
        {"time": datetime(2026, 11, 9, 14, 0), "kind": "auto", "lux": 1, "before": [60, 55], "after": [50, 45]},
        {"time": datetime(2026, 11, 9, 15, 0), "kind": "hand", "lux": 1, "before": [50, 45], "after": [55, 50]},
        {"time": datetime(2026, 11, 9, 16, 0), "kind": "joystick", "lux": 1, "before": [55, 50], "after": [70, 50]},
        {"time": datetime(2026, 11, 10, 9, 0), "kind": "auto", "lux": 1, "before": [55, 50], "after": [60, 55]},
    ]
    sun = {"dawn": 434, "sunrise": 472, "noon": 743, "sunset": 1013, "dusk": 1051}
    out = summarize(date(2026, 11, 9), minutes_from([(600, 50)]), ev, sun, threshold=10)
    assert out["auto"] == 1
    assert out["hand"] == 1
    assert out["joystick"] == 1
    assert out["writes"] == 15     # 10 steps + 5 steps, each step goes to both monitors at once


def test_collect_without_location(tmp_path):
    from yarilo.report import collect
    Recorder(tmp_path).sample(datetime(2026, 11, 9, 14, 0, 2), 13.7, [50, 45], "auto")
    data = collect(tmp_path, None)
    assert data["location"] == ""
    assert data["days"][0]["sun"] is None
    assert data["days"][0]["sum"]["at_sunset"] is None
