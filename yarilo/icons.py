"""Tray icon: a sun. Yellow - working, grey - paused, red dot - the sensor is silent."""
import math

from PIL import Image, ImageDraw

_COLOURS = {"on": (245, 180, 0, 255), "paused": (150, 150, 150, 255)}


def image(state: str, sensor_down: bool = False, size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = _COLOURS.get(state, _COLOURS["paused"])
    mid, r = size / 2, size * 0.2
    w = max(2, size // 12)
    for k in range(8):
        a = k * math.pi / 4
        x0, y0 = mid + math.cos(a) * r * 1.45, mid + math.sin(a) * r * 1.45
        x1, y1 = mid + math.cos(a) * r * 2.3, mid + math.sin(a) * r * 2.3
        d.line([(x0, y0), (x1, y1)], fill=c, width=w)
    d.ellipse([mid - r, mid - r, mid + r, mid + r], fill=c)
    if sensor_down:
        s = size * 0.36
        d.ellipse([size - s, size - s, size - 1, size - 1], fill=(220, 40, 40, 255))
    return img
