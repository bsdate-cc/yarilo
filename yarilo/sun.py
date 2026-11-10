"""How high the sun is here and now, and how much of the day curve to use."""
from datetime import datetime


def sun_elevation(when: datetime, lat: float, lon: float) -> float:
    """Degrees above the horizon (negative below); `when` must carry its time zone."""
    from astral import Observer
    from astral.sun import elevation
    return elevation(Observer(lat, lon), when)


def day_weight(elevation: float, night_below: float = -6.0, day_above: float = 3.0) -> float:
    """1 - the day curve, 0 - the night curve, linear through twilight in between."""
    if elevation <= night_below:
        return 0.0
    if elevation >= day_above:
        return 1.0
    return (elevation - night_below) / (day_above - night_below)
