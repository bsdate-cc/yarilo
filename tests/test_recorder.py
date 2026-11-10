from datetime import datetime

from yarilo.recorder import Recorder


def lines(p):
    return p.read_text(encoding="utf-8").splitlines()


def test_sample_goes_to_daily_file_with_header(tmp_path):
    r = Recorder(tmp_path)
    r.sample(datetime(2026, 11, 9, 14, 0, 2), 13.69586, [50, 45], "auto")
    r.sample(datetime(2026, 11, 9, 14, 0, 4), None, [50, 45], "auto")
    assert lines(tmp_path / "lux-2026-11-09.csv") == [
        "time,lux,monitors,mode",
        "2026-11-09T14:00:02,13.7,50/45,auto",
        "2026-11-09T14:00:04,,50/45,auto",
    ]


def test_new_day_goes_to_new_file(tmp_path):
    r = Recorder(tmp_path)
    r.sample(datetime(2026, 11, 9, 23, 59, 59), 1.0, [50, 45], "auto")
    r.sample(datetime(2026, 11, 10, 0, 0, 1), 1.0, [50, 45], "off")
    assert lines(tmp_path / "lux-2026-11-09.csv")[1:] == ["2026-11-09T23:59:59,1.0,50/45,auto"]
    assert lines(tmp_path / "lux-2026-11-10.csv") == [
        "time,lux,monitors,mode",
        "2026-11-10T00:00:01,1.0,50/45,off",
    ]


def test_unknown_brightness_is_empty(tmp_path):
    r = Recorder(tmp_path)
    r.sample(datetime(2026, 11, 9, 14, 0, 0), 5.0, None, "auto")
    assert lines(tmp_path / "lux-2026-11-09.csv")[1] == "2026-11-09T14:00:00,5.0,,auto"


def test_restart_appends_without_second_header(tmp_path):
    Recorder(tmp_path).sample(datetime(2026, 11, 9, 14, 0, 0), 5.0, [50, 45], "auto")
    Recorder(tmp_path).sample(datetime(2026, 11, 9, 14, 0, 2), 6.0, [50, 45], "auto")
    assert lines(tmp_path / "lux-2026-11-09.csv") == [
        "time,lux,monitors,mode",
        "2026-11-09T14:00:00,5.0,50/45,auto",
        "2026-11-09T14:00:02,6.0,50/45,auto",
    ]


def test_event_log(tmp_path):
    r = Recorder(tmp_path)
    r.event(datetime(2026, 11, 9, 14, 1, 0), "hand", 13.7, [50, 45], [55, 50])
    r.event(datetime(2026, 11, 9, 14, 2, 0), "off", None, None, None)
    assert lines(tmp_path / "events.csv") == [
        "time,kind,lux,before,after",
        "2026-11-09T14:01:00,hand,13.7,50/45,55/50",
        "2026-11-09T14:02:00,off,,,",
    ]
