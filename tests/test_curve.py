import pytest
from yarilo.curve import brightness_for

PTS = [(3.0, 25), (30.0, 55), (300.0, 90)]


def test_exact_points():
    assert brightness_for(PTS, 30) == pytest.approx(55)
    assert brightness_for(PTS, 300) == pytest.approx(90)


def test_interpolates_on_log_lux():
    # 3 -> 30 is one decade; its middle on the log scale is ~9.49 lx
    assert brightness_for(PTS, 3 * 10 ** 0.5) == pytest.approx(40)


def test_flat_beyond_ends():
    assert brightness_for(PTS, 0) == 25
    assert brightness_for(PTS, 0.01) == 25
    assert brightness_for(PTS, 5000) == 90

