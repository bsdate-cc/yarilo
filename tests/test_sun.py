from datetime import datetime, timedelta, timezone

import pytest

from yarilo.sun import day_weight, sun_elevation

MOSCOW = (55.75, 37.62)
TZ = timezone(timedelta(hours=3))


def test_day_weight_edges():
    assert day_weight(-10) == 0
    assert day_weight(-6) == 0
    assert day_weight(3) == 1
    assert day_weight(30) == 1


def test_day_weight_goes_linearly_through_twilight():
    assert day_weight(-1.5) == pytest.approx(0.5)
    assert day_weight(0, night_below=-4, day_above=4) == pytest.approx(0.5)


def test_moscow_noon_is_high_and_evening_is_dark():
    noon = sun_elevation(datetime(2026, 11, 10, 12, 13, tzinfo=TZ), *MOSCOW)
    assert 16 < noon < 18          # 90 - 55.75 - 17 (November declination)
    evening = sun_elevation(datetime(2026, 11, 10, 19, 30, tzinfo=TZ), *MOSCOW)
    assert evening < -6


def test_sunset_is_near_zero():
    at_sunset = sun_elevation(datetime(2026, 11, 10, 16, 31, tzinfo=TZ), *MOSCOW)
    assert -1.5 < at_sunset < 0.5   # refraction puts the visible sunset a little below 0
