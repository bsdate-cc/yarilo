"""System-wide hotkeys ("ctrl+alt+up") through RegisterHotKey, on a thread of their own."""
import ctypes
import logging
import threading
from ctypes import wintypes as W

log = logging.getLogger("yarilo")

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
_MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN}
_KEYS = {
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "pageup": 0x21, "pagedown": 0x22, "home": 0x24, "end": 0x23,
    "plus": 0xBB, "minus": 0xBD, "num+": 0x6B, "num-": 0x6D,
    "space": 0x20, "insert": 0x2D, "delete": 0x2E,
}
_KEYS.update({f"f{i}": 0x6F + i for i in range(1, 25)})
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012


def parse_hotkey(spec: str):
    """'ctrl+alt+up' -> (modifiers, virtual key); '' -> None; nonsense -> ValueError."""
    spec = (spec or "").strip().lower().replace(" ", "")
    if not spec:
        return None
    # "num+" / "num-" end with a sign that is also the separator
    tail = None
    for special in ("num+", "num-"):
        if spec == special or spec.endswith("+" + special):
            tail, spec = special, spec[: -len(special)].rstrip("+")
            break
    parts = [p for p in spec.split("+")] if spec else []
    if tail is None:
        if not parts or not parts[-1]:
            raise ValueError(f"no key in {spec!r}")
        tail, parts = parts[-1], parts[:-1]
    mods = 0
    for p in parts:
        if p not in _MODS:
            raise ValueError(f"unknown modifier {p!r}")
        mods |= _MODS[p]
    if tail in _KEYS:
        key = _KEYS[tail]
    elif len(tail) == 1 and tail.isalnum():
        key = ord(tail.upper())
    else:
        raise ValueError(f"unknown key {tail!r}")
    if not mods:
        raise ValueError("a hotkey needs ctrl, alt, shift or win")
    return mods, key


class Hotkeys(threading.Thread):
    """Registers {name: spec} and calls on_press(name); a bad or taken hotkey is logged."""

    def __init__(self, specs: dict, on_press):
        super().__init__(name="hotkeys", daemon=True)
        self.specs, self.on_press = specs, on_press
        self.failed: list[str] = []
        self._tid = None
        self._ready = threading.Event()

    def run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._tid = kernel32.GetCurrentThreadId()
        names = {}
        for i, (name, spec) in enumerate(self.specs.items(), start=1):
            try:
                parsed = parse_hotkey(spec)
            except ValueError as e:
                log.warning("hotkey %s=%r: %s", name, spec, e)
                self.failed.append(name)
                continue
            if parsed is None:
                continue
            if user32.RegisterHotKey(None, i, parsed[0] | MOD_NOREPEAT, parsed[1]):
                names[i] = name
            else:
                log.warning("hotkey %s=%r is taken by another program", name, spec)
                self.failed.append(name)
        self._ready.set()
        msg = W.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in names:
                try:
                    self.on_press(names[msg.wParam])
                except Exception:
                    log.exception("hotkey")
        for i in names:
            user32.UnregisterHotKey(None, i)

    def stop(self):
        self._ready.wait(2)
        if self._tid:
            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
