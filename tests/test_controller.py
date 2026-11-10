import pytest

from yarilo.controller import Controller, Settings, monitor_values, base_from

PTS = [(3.0, 25), (30.0, 55), (300.0, 90)]


def make(applied=55, **kw):
    c = Controller(Settings(**kw), PTS)
    c.applied = applied
    return c


def feed(c, t0, t1, lux, every=2):
    t = t0
    while t <= t1:
        c.add_sample(t, lux)
        t += every


def test_no_samples_no_change():
    assert make().decide(100) is None


def test_small_difference_is_ignored():
    c = make()
    feed(c, 0, 200, 33)            # target ~56.4, difference < 4
    assert c.decide(200) is None


def test_change_after_hold():
    c = make()
    feed(c, 0, 60, 60)             # target ~65.5, difference ~10.5 < fast_jump
    assert c.decide(20) is None    # timer starts
    assert c.decide(49) is None
    assert c.decide(50) == 65      # held 30 s -> rounded to a step of 5


def test_big_jump_uses_fast_hold():
    c = make()
    feed(c, 0, 20, 300)            # target 90, difference 35
    assert c.decide(10) is None
    assert c.decide(15) == 90


def test_timer_resets_when_difference_disappears():
    c = make()
    feed(c, 0, 20, 60)
    assert c.decide(20) is None
    feed(c, 22, 60, 30)            # back to the current level
    assert c.decide(45) is None
    feed(c, 62, 120, 60)
    assert c.decide(85) is None    # a new timer starts at 85, not at 20
    assert c.decide(114) is None
    assert c.decide(115) == 65


def test_direction_flip_restarts_timer():
    c = make()
    feed(c, 0, 20, 60)             # brighter
    assert c.decide(20) is None
    feed(c, 22, 80, 12)            # then darker: target ~43.1, difference ~ -11.9
    assert c.decide(45) is None    # direction flipped at 45 -> timer restarts
    assert c.decide(74) is None
    assert c.decide(75) == 45


def test_short_spike_is_filtered_by_median():
    c = make()
    feed(c, 0, 40, 30)
    c.add_sample(42, 0.0)          # finger over the sensor
    c.add_sample(44, 0.0)
    feed(c, 46, 120, 30)
    for t in range(42, 121, 2):
        assert c.decide(t) is None


def test_stale_sensor_means_no_decision():
    c = make()
    feed(c, 0, 20, 300)
    assert c.decide(60) is None    # the last sample is 40 s old


def test_first_write_when_current_unknown():
    c = make(applied=None)
    feed(c, 0, 4, 30)
    assert c.decide(4) == 55


def test_paused_by_user():
    c = make()
    c.user_paused = True
    feed(c, 0, 20, 300)
    assert c.decide(5) is None
    assert c.decide(30) is None


def test_manual_pause_expires():
    c = make(manual_pause_s=600)
    c.pause_for_manual(0)
    assert c.paused_until == 600
    feed(c, 590, 610, 300)
    assert c.decide(595) is None
    assert c.decide(600) is None   # pause is over, the timer starts
    assert c.decide(605) == 90


def test_result_is_clamped():
    c = make(applied=70, max_b=80)
    feed(c, 0, 60, 300)            # raw target 90 is clamped to 80: difference 10, normal hold
    assert c.decide(10) is None
    assert c.decide(39) is None
    assert c.decide(40) == 80


def test_nudge_switches_auto_off_without_learning():
    c = make()
    feed(c, 0, 20, 30)
    assert c.nudge(20, +5) == 60
    assert c.applied == 60
    assert c.user_paused
    assert c.day_points == PTS
    feed(c, 22, 200, 300)
    assert all(c.decide(t) is None for t in range(22, 201, 2))


def test_nudge_without_light_only_changes():
    c = make()
    assert c.nudge(0, -5) == 50
    assert c.day_points == PTS


def test_nudge_clamped():
    c = make(applied=100)
    feed(c, 0, 4, 30)
    assert c.nudge(4, +5) is None


def test_nudge_unknown_current():
    c = make(applied=None)
    assert c.nudge(0, +5) is None


def test_monitor_values_with_offsets():
    assert monitor_values(55, [5, 0]) == [60, 55]
    assert monitor_values(98, [5, 0]) == [100, 98]
    assert monitor_values(3, [0, -5]) == [3, 0]


def test_monitor_values_more_monitors_than_offsets():
    assert monitor_values(55, [5]) == [60]
    assert monitor_values(55, [5], count=3) == [60, 55, 55]


def test_base_from_reference_monitor():
    # the reference is the monitor whose offset is closest to zero
    assert base_from([60, 55], [5, 0]) == 55
    assert base_from([60], [5]) == 55


def test_set_by_hand_switches_auto_off_without_learning():
    c = make()
    feed(c, 0, 20, 30)
    assert c.set_by_hand(20, 72) == 72
    assert c.applied == 72
    assert c.user_paused
    assert c.day_points == PTS
    assert c.target(20) == 55


def test_set_by_hand_clamps_and_clears_manual_pause():
    c = make(min_b=10)
    c.pause_for_manual(0)
    assert c.set_by_hand(5, 3) == 10
    assert c.paused_until is None


NIGHT = [(3.0, 0), (8.0, 10), (30.0, 40), (300.0, 90)]


def test_day_and_night_curves_blend_by_sun():
    c = Controller(Settings(), PTS, NIGHT)
    c.applied = 55
    feed(c, 0, 20, 30)
    c.day_weight = 1.0
    assert c.target(20) == pytest.approx(55)
    c.day_weight = 0.0
    assert c.target(20) == pytest.approx(40)
    c.day_weight = 0.5
    assert c.target(20) == pytest.approx(47.5)


def test_night_curve_defaults_to_day_curve():
    c = Controller(Settings(), PTS)
    c.day_weight = 0.0
    feed(c, 0, 20, 30)
    assert c.target(20) == pytest.approx(55)


def test_numbered_skips_monitors():
    from yarilo.controller import numbered
    assert numbered(["a", "b", "c"], skip=[2]) == [(1, "a"), (3, "c")]
    assert numbered(["a", "b"], skip=[]) == [(1, "a"), (2, "b")]


def test_offsets_follow_monitor_numbers():
    from yarilo.controller import offsets_for
    assert offsets_for([1, 3], [5, 0, -5]) == [5, -5]
    assert offsets_for([1, 2, 3], [5]) == [5, 0, 0]
