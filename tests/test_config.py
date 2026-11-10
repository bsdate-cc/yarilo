import json

from yarilo.config import DEFAULTS, load, save


def test_missing_file_gives_defaults(tmp_path):
    cfg = load(tmp_path / "config.json")
    assert cfg == DEFAULTS
    assert not (tmp_path / "config.json").exists()


def test_defaults_are_slider_only():
    assert DEFAULTS["sensor_urls"] == []
    assert DEFAULTS["location"] is None
    assert DEFAULTS["monitor_offsets"] == []
    assert DEFAULTS["hotkeys"] == {"brighter": "", "darker": ""}


def test_partial_file_is_merged(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"hold_s": 45}), encoding="utf-8")
    cfg = load(p)
    assert cfg["hold_s"] == 45
    assert cfg["step"] == DEFAULTS["step"]


def test_broken_file_is_kept_aside(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json", encoding="utf-8")
    cfg = load(p)
    assert cfg == DEFAULTS
    assert (tmp_path / "config.json.bad").read_text(encoding="utf-8") == "{not json"


def test_save_roundtrip(tmp_path):
    p = tmp_path / "sub" / "config.json"
    cfg = dict(DEFAULTS, points_day=[[5, 30], [50, 60]])
    save(p, cfg)
    assert load(p)["points_day"] == [[5, 30], [50, 60]]


def test_defaults_not_shared(tmp_path):
    cfg = load(tmp_path / "config.json")
    cfg["points_night"].append([1, 1])
    cfg["hotkeys"]["brighter"] = "ctrl+alt+up"
    assert [1, 1] not in DEFAULTS["points_night"]
    assert DEFAULTS["hotkeys"]["brighter"] == ""
