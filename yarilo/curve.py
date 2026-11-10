"""Light -> brightness curve: a few (lux, brightness) points joined on a log-lux scale."""
import math

MIN_LUX = 0.5          # below this the sensor reads "dark"; keeps log() defined

Point = tuple[float, int]


def brightness_for(points: list[Point], lux: float) -> float:
    """Brightness for this light; flat beyond the first and the last point."""
    pts = sorted(points)
    x = math.log10(max(lux, MIN_LUX))
    if x <= math.log10(pts[0][0]):
        return float(pts[0][1])
    for (l0, b0), (l1, b1) in zip(pts, pts[1:]):
        x0, x1 = math.log10(l0), math.log10(l1)
        if x <= x1:
            return b0 + (b1 - b0) * (x - x0) / (x1 - x0)
    return float(pts[-1][1])

