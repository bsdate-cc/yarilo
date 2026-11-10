"""When and to what to change the brightness. No I/O here: time is passed in."""
import math
from collections import deque
from dataclasses import dataclass
from statistics import median

from .curve import brightness_for


@dataclass
class Settings:
    window_s: float = 20       # median over this long: a finger or a shadow is ignored
    stale_s: float = 30        # no sample this long -> the sensor is down, change nothing
    threshold: float = 4       # dead band around the current brightness
    step: int = 5              # new values are multiples of this
    hold_s: float = 30         # the difference must last this long
    fast_jump: float = 15      # ...or this much bigger (room light switched on)
    fast_hold_s: float = 5     # ...for only this long
    min_b: int = 10
    max_b: int = 100
    manual_pause_s: float = 3600   # brightness changed by hand -> leave it alone this long


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _pts(points):
    return [(float(l), int(b)) for l, b in points]


class Controller:
    def __init__(self, settings: Settings, day_points, night_points=None):
        self.s = settings
        self.day_points = _pts(day_points)
        self.night_points = _pts(night_points if night_points is not None else day_points)
        self.day_weight = 1.0               # 1 - sun up, 0 - night; set from the sun
        self.samples: deque[tuple[float, float]] = deque()
        self.applied: int | None = None     # base brightness now on the monitors
        self.user_paused = False
        self.paused_until: float | None = None
        self._since: float | None = None    # when the current difference started
        self._sign = 0

    # --- light ---
    def add_sample(self, t: float, lux: float) -> None:
        self.samples.append((t, lux))
        keep = max(self.s.window_s, self.s.stale_s) * 2
        while self.samples and self.samples[0][0] < self.samples[-1][0] - keep:
            self.samples.popleft()

    def smoothed_lux(self, t: float) -> float | None:
        window = [lux for ts, lux in self.samples if t - self.s.window_s < ts <= t]
        last = max((ts for ts, _ in self.samples if ts <= t), default=None)
        if not window or last is None or t - last > self.s.stale_s:
            return None
        return median(window)

    def target(self, t: float) -> float | None:
        lux = self.smoothed_lux(t)
        if lux is None:
            return None
        w = self.day_weight
        b = w * brightness_for(self.day_points, lux) + (1 - w) * brightness_for(self.night_points, lux)
        return _clamp(b, self.s.min_b, self.s.max_b)

    # --- pauses ---
    def pause_for_manual(self, t: float) -> None:
        self.paused_until = t + self.s.manual_pause_s
        self._since = None

    def is_paused(self, t: float) -> bool:
        if self.paused_until is not None and t >= self.paused_until:
            self.paused_until = None
        return self.user_paused or self.paused_until is not None

    # --- decisions ---
    def quantize(self, x: float) -> int:
        return int(_clamp(self.s.step * round(x / self.s.step), self.s.min_b, self.s.max_b))

    def decide(self, t: float) -> int | None:
        """New base brightness to write now, or None."""
        if self.is_paused(t):
            return None
        target = self.target(t)
        if target is None:
            return None
        if self.applied is None:
            return self.quantize(target)
        diff = target - self.applied
        if abs(diff) < self.s.threshold:
            self._since = None
            return None
        sign = 1 if diff > 0 else -1
        if self._since is None or sign != self._sign:
            self._since, self._sign = t, sign
        hold = self.s.fast_hold_s if abs(diff) >= self.s.fast_jump else self.s.hold_s
        if t - self._since < hold:
            return None
        new = self.quantize(target)
        self._since = None
        return new if new != self.applied else None

    def set_by_hand(self, t: float, value: int) -> int:
        """The slider: either auto or by hand - auto goes off, the curve stays as it is."""
        new = int(_clamp(value, self.s.min_b, self.s.max_b))
        self.applied = new
        self.user_paused = True
        self.paused_until = None
        self._since = None
        return new

    def nudge(self, t: float, delta: int) -> int | None:
        """"Brighter/darker" from the menu: the same as the slider, by 5."""
        if self.applied is None:
            return None
        new = int(_clamp(self.applied + delta, self.s.min_b, self.s.max_b))
        if new == self.applied:
            return None
        return self.set_by_hand(t, new)


def ramp(start: list[int], end: list[int]) -> list[list[int]]:
    """Steps for a smooth change: the biggest change moves by 1 per step, the rest in proportion."""
    n = max((abs(e - s) for s, e in zip(start, end)), default=0)
    return [[int(math.floor(s + (e - s) * k / n + 0.5)) for s, e in zip(start, end)]
            for k in range(1, n + 1)]


def monitor_values(base: int, offsets: list[int], count: int | None = None) -> list[int]:
    """Values per monitor, left to right; monitors without an offset get none."""
    n = len(offsets) if count is None else count
    return [int(_clamp(base + (offsets[i] if i < len(offsets) else 0), 0, 100)) for i in range(n)]


def base_from(values: list[int], offsets: list[int]) -> int:
    """Base brightness read back from the monitor whose offset is closest to zero."""
    offs = [offsets[i] if i < len(offsets) else 0 for i in range(len(values))]
    ref = min(range(len(values)), key=lambda i: abs(offs[i]))
    return values[ref] - offs[ref]


def numbered(items: list, skip: list[int]) -> list[tuple[int, object]]:
    """Monitors numbered left to right from 1, without the skipped numbers."""
    return [(n, item) for n, item in enumerate(items, start=1) if n not in set(skip)]


def offsets_for(numbers: list[int], offsets: list[int]) -> list[int]:
    """The offset of each of these monitors; a monitor beyond the list gets none."""
    return [offsets[n - 1] if n - 1 < len(offsets) else 0 for n in numbers]
