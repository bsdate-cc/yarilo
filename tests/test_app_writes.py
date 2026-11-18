import pytest

import yarilo.app as appmod


@pytest.fixture
def env(monkeypatch, tmp_path):
    """App with two fake monitors (left, right); a monitor in `asleep` does not answer DDC."""
    state = {"vals": [5, 0], "asleep": set(), "writes": []}

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
        state["writes"].append((m, v))
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


def test_sleeping_monitors_are_asked_rarely(env, monkeypatch):
    app, state = env
    reads = []
    real_get = appmod.get_brightness

    def counting_get(m, code=0x10):
        reads.append(m)
        return real_get(m, code)
    monkeypatch.setattr(appmod, "get_brightness", counting_get)
    state["asleep"] = {0, 1}
    app.apply(5, t=100)                    # fails: both asleep
    reads.clear()
    for t in range(100, 160, 2):           # a tick every 2 s for a minute
        app.resync_if_unknown(t)
    assert len(reads) == 2                 # one attempt (two monitors), not thirty
    app.resync_if_unknown(161)
    assert len(reads) == 4                 # the next one a minute later


def test_no_auto_write_right_after_wake(env):
    app, state = env
    state["asleep"] = {0, 1}
    app.apply(5, t=100)
    state["asleep"] = set()
    app.resync_if_unknown(200)             # monitors are back
    assert app.expected == [5, 0]
    assert app.just_woke(205)
    assert not app.just_woke(211)
    app.ctl.day_points = app.ctl.night_points = [(1, 50), (300, 50)]
    for t in range(180, 212, 2):
        app.ctl.add_sample(t, 30)
    assert app.ctl.decide(211) == 1   # fresh catch-up, not the full target 50


def test_auto_apply_writes_exactly_one_step(env):
    app, state = env
    assert app.apply(5, t=10)
    assert state["vals"] == [10, 5]
    assert state["writes"] == [(0, 10), (1, 5)]


def test_failed_write_cancels_step_deadline(env):
    app, state = env
    state["vals"] = [50, 45]
    app.sync()
    app.ctl.s.hold_s = 0
    app.ctl.day_points = app.ctl.night_points = [(1, 80), (300, 80)]
    for t in range(0, 12, 2):
        app.ctl.add_sample(t, 30)
    assert app.apply(app.ctl.decide(10), 10)
    state["asleep"] = {1}
    assert app.apply(app.ctl.decide(13), 13) is False
    assert app.expected is None
    assert app.ctl.next_delay(100, poll_s=2) == 2


def test_removing_sensor_cancels_step_deadline(env):
    app, state = env
    state["vals"] = [50, 45]
    app.sync()
    app.ctl.s.hold_s = 0
    app.ctl.day_points = app.ctl.night_points = [(1, 80), (300, 80)]
    for t in range(0, 12, 2):
        app.ctl.add_sample(t, 30)
    assert app.apply(app.ctl.decide(10), 10)
    app.sensor = None
    app.cfg["record_light"] = False
    app.refresh = lambda: None
    app._tick()
    assert app.ctl.next_delay(100, poll_s=2) == 2


def test_auto_transition_logged_once(env):
    app, state = env
    state["vals"] = [50, 45]
    app.sync()                         # base=45
    app.ctl.s.hold_s = 0
    app.ctl.day_points = app.ctl.night_points = [(1, 50), (300, 50)]
    for t in range(0, 12, 2):
        app.ctl.add_sample(t, 30)
    app.apply(app.ctl.decide(10), 10)
    app.apply(app.ctl.decide(13), 13)  # base=47, target inside the dead band
    events = app.rec.folder.joinpath("events.csv").read_text(encoding="utf-8").splitlines()
    assert len(events) == 2
    assert events[1].endswith("auto,30.0,50/45,52/47")


def test_manual_change_finishes_auto_log_and_stays_immediate(env, monkeypatch):
    app, state = env
    state["vals"] = [50, 45]
    app.sync()
    app.ctl.s.hold_s = 0
    app.ctl.day_points = app.ctl.night_points = [(1, 80), (300, 80)]
    for t in range(0, 12, 2):
        app.ctl.add_sample(t, 30)
    app.apply(app.ctl.decide(10), 10)
    app.apply(app.ctl.decide(13), 13)
    monkeypatch.setattr(appmod.time, "monotonic", lambda: 20)
    app.refresh = lambda: None
    app.nudge(+5)
    assert state["vals"] == [57, 52]
    assert app.ctl.user_paused
    events = app.rec.folder.joinpath("events.csv").read_text(encoding="utf-8").splitlines()
    kinds = [line.split(",")[1] for line in events[1:]]
    assert kinds == ["auto", "off", "hand"]
    assert events[1].endswith("auto,30.0,50/45,52/47")


def test_startup_sync_requests_catchup(env, monkeypatch):
    app, _state = env
    app.ctl.day_points = app.ctl.night_points = [(1, 50), (300, 50)]
    for t in range(0, 12, 2):
        app.ctl.add_sample(t, 30)
    monkeypatch.setattr(appmod.time, "monotonic", lambda: 10)
    app.refresh = lambda: None
    app.stop.set()                    # initial sync still runs; no loop iterations
    app.loop()
    assert app.ctl.decide(20) == 1    # without catch-up the normal hold would return None


def test_tick_discards_samples_after_long_gap(env, monkeypatch):
    app, _state = env
    light = {"lux": 300.0}

    class Sensor:
        last_error = None

        def read(self):
            return light["lux"]

    app.sensor = Sensor()
    app.ctl.user_paused = True
    app.cfg["record_light"] = False
    app.refresh = lambda: None
    times = iter([100, 200])
    monkeypatch.setattr(appmod.time, "monotonic", lambda: next(times))
    app._tick()
    light["lux"] = 30.0
    app._tick()
    assert list(app.ctl.samples) == [(200, 30.0)]


def test_sensor_recovery_discards_old_samples(env, monkeypatch):
    app, _state = env
    light = {"lux": 300.0}

    class Sensor:
        last_error = None

        def read(self):
            return light["lux"]

    app.sensor = Sensor()
    app.ctl.user_paused = True
    app.cfg["record_light"] = False
    app.refresh = lambda: None
    times = iter([0, 20, 40, 50])
    monkeypatch.setattr(appmod.time, "monotonic", lambda: next(times))
    app._tick()
    light["lux"] = None
    app._tick()
    app._tick()                       # sensor_down at t=40
    light["lux"] = 30.0
    app._tick()                       # recovery at t=50, no long loop gap
    assert list(app.ctl.samples) == [(50, 30.0)]
