"""Monitor brightness over DDC/CI (dxva2). Monitors come ordered left to right.

Brightness is in percent here: a monitor whose maximum is not 100 (some report 255) is scaled.
"""
import ctypes
import re
from ctypes import wintypes as W
from dataclasses import dataclass

VCP_BRIGHTNESS = 0x10

_user32 = ctypes.WinDLL("user32")
_dxva2 = ctypes.WinDLL("dxva2")


class _PhysicalMonitor(ctypes.Structure):
    _fields_ = [("handle", W.HANDLE), ("description", W.WCHAR * 128)]


class _MonitorInfoEx(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT),
                ("dwFlags", W.DWORD), ("szDevice", W.WCHAR * 32)]


_EnumProc = ctypes.WINFUNCTYPE(W.BOOL, W.HMONITOR, W.HDC, ctypes.POINTER(W.RECT), W.LPARAM)
_user32.EnumDisplayMonitors.argtypes = [W.HDC, ctypes.POINTER(W.RECT), _EnumProc, W.LPARAM]
_user32.GetMonitorInfoW.argtypes = [W.HMONITOR, ctypes.POINTER(_MonitorInfoEx)]
_dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [W.HMONITOR, ctypes.POINTER(W.DWORD)]
_dxva2.GetPhysicalMonitorsFromHMONITOR.argtypes = [W.HMONITOR, W.DWORD, ctypes.POINTER(_PhysicalMonitor)]
_dxva2.DestroyPhysicalMonitors.argtypes = [W.DWORD, ctypes.POINTER(_PhysicalMonitor)]
_dxva2.GetVCPFeatureAndVCPFeatureReply.argtypes = [
    W.HANDLE, W.BYTE, ctypes.c_void_p, ctypes.POINTER(W.DWORD), ctypes.POINTER(W.DWORD)]
_dxva2.SetVCPFeature.argtypes = [W.HANDLE, W.BYTE, W.DWORD]
_dxva2.GetCapabilitiesStringLength.argtypes = [W.HANDLE, ctypes.POINTER(W.DWORD)]
_dxva2.CapabilitiesRequestAndCapabilitiesReply.argtypes = [W.HANDLE, ctypes.c_char_p, W.DWORD]


@dataclass
class Monitor:
    device: str        # \\.\DISPLAY1
    left: int          # x of the left edge on the desktop
    top: int
    width: int
    height: int
    description: str   # what Windows calls it, often "Generic PnP Monitor"
    handle: int

    @property
    def key(self):
        return (self.device, self.left, self.top)


class Monitors:
    """with Monitors() as ms: ...  - physical monitor handles, released on exit."""

    def __enter__(self) -> list[Monitor]:
        self._arrays = []
        found: list[Monitor] = []

        def on_monitor(hmon, hdc, rect, lparam):
            info = _MonitorInfoEx()
            info.cbSize = ctypes.sizeof(info)
            _user32.GetMonitorInfoW(hmon, ctypes.byref(info))
            r = info.rcMonitor
            n = W.DWORD()
            if not _dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(n)) or not n.value:
                return True
            arr = (_PhysicalMonitor * n.value)()
            if _dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, n, arr):
                self._arrays.append((n.value, arr))
                for pm in arr:
                    found.append(Monitor(info.szDevice, r.left, r.top, r.right - r.left, r.bottom - r.top,
                                         pm.description, pm.handle))
            return True

        _user32.EnumDisplayMonitors(None, None, _EnumProc(on_monitor), 0)
        return sorted(found, key=lambda m: (m.left, m.top))

    def __exit__(self, *exc):
        for n, arr in self._arrays:
            _dxva2.DestroyPhysicalMonitors(n, arr)
        return False


_max_seen: dict = {}   # monitor key -> the maximum it reported for a VCP code


def get_vcp(m: Monitor, code: int = VCP_BRIGHTNESS):
    """(current, maximum) as the monitor reports them, or None."""
    cur, mx = W.DWORD(), W.DWORD()
    for _ in range(2):   # DDC answers sometimes get lost; one retry is enough
        if _dxva2.GetVCPFeatureAndVCPFeatureReply(m.handle, code, None, ctypes.byref(cur), ctypes.byref(mx)):
            _max_seen[(m.key, code)] = int(mx.value) or 100
            return int(cur.value), int(mx.value)
    return None


def set_vcp(m: Monitor, code: int, value: int) -> bool:
    for _ in range(2):
        if _dxva2.SetVCPFeature(m.handle, code, int(value)):
            return True
    return False


def get_brightness(m: Monitor, code: int = VCP_BRIGHTNESS) -> int | None:
    got = get_vcp(m, code)
    if got is None:
        return None
    cur, mx = got
    return round(cur * 100 / mx) if mx and mx != 100 else cur


def set_brightness(m: Monitor, percent: int, code: int = VCP_BRIGHTNESS) -> bool:
    mx = _max_seen.get((m.key, code))
    if mx is None:
        if get_vcp(m, code) is None:
            return False
        mx = _max_seen[(m.key, code)]
    return set_vcp(m, code, round(percent * mx / 100) if mx != 100 else percent)


def capabilities(m: Monitor) -> str | None:
    """The capabilities string the monitor sends (slow: up to a few seconds), or None."""
    n = W.DWORD()
    if not _dxva2.GetCapabilitiesStringLength(m.handle, ctypes.byref(n)) or not n.value:
        return None
    buf = ctypes.create_string_buffer(n.value)
    if not _dxva2.CapabilitiesRequestAndCapabilitiesReply(m.handle, buf, n.value):
        return None
    return buf.value.decode("ascii", "replace")


def vcp_codes(caps: str) -> list[int]:
    """VCP codes listed in a capabilities string: 'vcp(02 04 10 12 14(05 08 0B) ...)'."""
    m = re.search(r"vcp\((.*)", caps or "", re.IGNORECASE)
    if not m:
        return []
    depth, out, token = 1, [], ""
    for ch in m.group(1):
        if ch == "(":
            if depth == 1 and token:
                out.append(int(token, 16))
                token = ""
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
        elif depth == 1:
            if ch.isspace():
                if token:
                    out.append(int(token, 16))
                    token = ""
            elif ch in "0123456789abcdefABCDEF":
                token += ch
    if token:
        out.append(int(token, 16))
    return out
