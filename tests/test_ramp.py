from yarilo.controller import ramp


def test_ramp_steps_by_one_on_the_biggest_change():
    assert ramp([50, 45], [55, 50]) == [[51, 46], [52, 47], [53, 48], [54, 49], [55, 50]]


def test_ramp_down():
    assert ramp([50, 45], [47, 42]) == [[49, 44], [48, 43], [47, 42]]


def test_ramp_other_monitor_follows_proportionally():
    # left clamps at 100 earlier than right
    steps = ramp([95, 90], [100, 100])
    assert steps[-1] == [100, 100]
    assert len(steps) == 10
    for prev, cur in zip(steps, steps[1:]):
        assert all(p <= c for p, c in zip(prev, cur))


def test_ramp_nothing_to_do():
    assert ramp([50, 45], [50, 45]) == []


def test_ramp_ends_exactly_on_target():
    assert ramp([10, 10], [45, 40])[-1] == [45, 40]
    assert len(ramp([10, 10], [45, 40])) == 35
