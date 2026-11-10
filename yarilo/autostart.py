"""Start with Windows through HKCU\\...\\Run."""
import sys
from pathlib import Path

_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "Yarilo"
ROOT = Path(__file__).resolve().parents[1]


def command() -> str:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{ROOT / "yarilo.pyw"}"'


def is_enabled() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as key:
            winreg.QueryValueEx(key, NAME)
        return True
    except OSError:
        return False


def enable() -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command())


def disable() -> None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, NAME)
    except OSError:
        pass
