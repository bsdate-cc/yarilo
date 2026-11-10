import pytest

import yarilo.app as appmod


@pytest.fixture
def env(monkeypatch, tmp_path):
    """App with two fake monitors (left, right); a monitor in `asleep` does not answer DDC."""
    state = {"vals": [5, 0], "asleep": set()}

    class Mons:
        def __enter__(self):
            return [0, 1]

        def __exit__(self, *exc):
            return False

    def get(m, code=0x10):
        return None if m in state["asleep"] else state["vals"][m]

    def put(m, v, code=0x10):
        if m in state["asleep"]:
            return False
        state["vals"][m] = v
        return True

    class Icon:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr(appmod, "Monitors", Mons)
    monkeypatch.setattr(appmod, "get_brightness", get)
    monkeypatch.setattr(appmod, "set_brightness", put)
    monkeypatch.setattr(appmod.pystray, "Icon", Icon)
    monkeypatch.setattr(appmod.config, "DATA_DIR", tmp_path)
    app = appmod.App(cfg_path=tmp_path / "config.json")
    app.cfg["smooth"] = False
    app.cfg["monitor_offsets"] = [5, 0]        # the left one gets +5
    app.cfg["sensor_urls"] = ["http://sensor/"]
    app.sensor = app._make_sensor()
    app.sync()
    return app, state


def test_half_failed_write_is_not_taken_for_monitor_buttons(env):
    app, state = env
    state["asleep"] = {1}                 # right monitor asleep, left awake
    assert app.apply(5, t=100) is False   # left goes to 10, right does not answer
    assert state["vals"] == [10, 0]
    state["asleep"] = set()
    assert app.apply(5, t=200) is True
    assert app.ctl.paused_until is None
    assert state["vals"] == [10, 5]


def test_monitor_buttons_are_still_noticed(env):
    app, state = env
    state["vals"][1] = 20                 # right changed with its own buttons
    assert app.apply(5, t=100) is False
    assert app.ctl.paused_until == 100 + app.ctl.s.manual_pause_s
    assert state["vals"] == [5, 20]


def test_failed_write_is_resynced_on_next_tick(env):
    app, state = env
    state["asleep"] = {1}
    app.apply(5, t=100)
    state["asleep"] = set()
    app.resync_if_unknown()
    assert app.expected == [10, 0]
