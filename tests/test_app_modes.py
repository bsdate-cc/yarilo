import pytest

import yarilo.app as appmod


@pytest.fixture
def make(monkeypatch, tmp_path):
    """make(vals, **cfg) -> (app, state) with fake monitors left to right."""
    def factory(vals, **cfg):
        state = {"vals": list(vals), "writes": []}

        class Mons:
            def __enter__(self):
                return list(range(len(state["vals"])))

            def __exit__(self, *exc):
                return False

        def put(m, v, code=0x10):
            state["vals"][m] = v
            state["writes"].append((m, v))
            return True

        class Icon:
            def __init__(self, *a, **k):
                pass

        monkeypatch.setattr(appmod, "Monitors", Mons)
        monkeypatch.setattr(appmod, "get_brightness", lambda m, code=0x10: state["vals"][m])
        monkeypatch.setattr(appmod, "set_brightness", put)
        monkeypatch.setattr(appmod.pystray, "Icon", Icon)
        monkeypatch.setattr(appmod.config, "DATA_DIR", tmp_path)
        app = appmod.App(cfg_path=tmp_path / "config.json")
        app.cfg.update(cfg)
        app.sensor = app._make_sensor()
        app.refresh = lambda: None
        app.sync()
        return app, state
    return factory


def test_without_a_sensor_it_is_a_slider(make):
    app, _ = make([40, 60])
    assert not app.has_sensor
    assert not app.auto_on()
    assert "40 / 60" in app.status_line()


def test_brighter_moves_each_monitor_from_its_own_value(make):
    app, state = make([40, 60])
    app.brighter()
    assert state["vals"] == [45, 65]
    app.darker()
    app.darker()
    assert state["vals"] == [35, 55]


def test_brighter_stops_at_max(make):
    app, state = make([98, 60], max=100)
    app.brighter()
    assert state["vals"] == [100, 65]


def test_one_slider_moves_one_monitor(make):
    app, state = make([40, 60])
    app.slider_begin()
    app.slider_preview(70, number=2)
    app.slider_commit(72, number=2)
    assert state["vals"] == [40, 72]


def test_linked_slider_keeps_offsets(make):
    app, state = make([40, 60], monitor_offsets=[5, 0])
    app.slider_commit(50)
    assert state["vals"] == [55, 50]


def test_skipped_monitor_is_never_touched(make):
    app, state = make([40, 60, 70], skip_monitors=[2])
    app.brighter()
    assert state["vals"] == [45, 60, 75]
    assert all(m != 1 for m, _v in state["writes"])


def test_slider_turns_auto_off_with_a_sensor(make):
    app, _ = make([40, 60], sensor_urls=["http://sensor/x"])
    assert app.auto_on()
    app.slider_commit(30)
    assert not app.auto_on()


def test_dragging_is_not_logged_as_events(make, tmp_path):
    app, _ = make([40, 60], sensor_urls=["http://sensor/x"])
    for v in range(41, 50):
        app.slider_preview(v)
    assert not (tmp_path / "lux" / "events.csv").exists()
    app.slider_commit(50)
    assert (tmp_path / "lux" / "events.csv").read_text(encoding="utf-8").count("\n") == 3   # header, off, hand


@pytest.mark.parametrize("start, offset, target, second_base", [
    (0, -5, 0, 3),       # lower clamp: base 5 -> 4 -> 3 while physical value stays 0
    (100, 5, 100, 97),   # upper clamp: base 95 -> 96 -> 97 while physical value stays 100
], ids=["lower", "upper"])
def test_clamped_offset_does_not_repeat_forever(make, start, offset, target, second_base):
    app, _state = make([start], sensor_urls=["http://sensor/x"], monitor_offsets=[offset])
    app.ctl.s.hold_s = 0
    app.ctl.day_points = app.ctl.night_points = [(1, target), (300, target)]
    for t in range(0, 12, 2):
        app.ctl.add_sample(t, 30)
    assert app.apply(app.ctl.decide(10), 10)
    assert app.apply(app.ctl.decide(13), 13)
    assert app.ctl.applied == second_base
    assert app.ctl.decide(16) is None
    events = app.rec.folder.joinpath("events.csv").read_text(encoding="utf-8").splitlines()
    assert len(events) == 2             # header and one logical auto transition
