"""What the user reads - in Russian or English. Russian is the source language: the code says
`_("Выход")` and the English text is looked up here; a text without a translation is shown as
it is (a test checks that there is none). Logs are not translated."""
import ctypes

LANG_RUSSIAN = 0x19

EN = {
    # tray
    "Ярило": "Yarilo",
    "Яркость…": "Brightness…",
    "Ярче": "Brighter",
    "Темнее": "Darker",
    "Автояркость": "Auto brightness",
    "Запускать при входе в Windows": "Start with Windows",
    "График света": "Light chart",
    "Открыть страницу датчика": "Open the sensor page",
    "Открыть настройки": "Open settings",
    "Выход": "Quit",
    "Ярило уже запущено — значок с солнцем в трее.": "Yarilo is already running — the sun icon in the tray.",
    # status
    "яркость": "brightness",
    "мониторы не отвечают": "the monitors do not answer",
    "датчик не отвечает": "the sensor does not answer",
    "с {time}": "since {time}",
    "{lux} лк": "{lux} lx",
    "день": "day",
    "ночь": "night",
    "сумерки": "twilight",
    "автояркость выключена": "auto brightness off",
    "пауза до {time}: меняли кнопками монитора": "paused until {time}: changed with the monitor buttons",
    "горячая клавиша не работает: {names}": "hotkey not working: {names}",
    # slider window
    "Яркость": "Brightness",
    "Вместе": "Together",
    "Все мониторы": "All monitors",
    "Монитор {n}": "Monitor {n}",
    "не отвечает по DDC/CI": "does not answer over DDC/CI",
    "Ползунок выключает автояркость; вернуть — галочкой": "The slider turns auto brightness off; tick it to bring it back",
}

_language = "ru"


def pick_language(ui: int, regional: int) -> str:
    """'ru' when Windows itself or its regional format is Russian, else 'en'."""
    return "ru" if LANG_RUSSIAN in (ui & 0x3FF, regional & 0x3FF) else "en"


def system_language() -> str:
    try:
        k = ctypes.windll.kernel32
        return pick_language(k.GetUserDefaultUILanguage(), k.GetUserDefaultLCID())
    except Exception:
        return "en"


def set_language(setting: str) -> None:
    """'ru' or 'en'; anything else ('auto') follows Windows."""
    global _language
    _language = setting if setting in ("ru", "en") else system_language()


def _(text: str, **values) -> str:
    out = EN.get(text, text) if _language == "en" else text
    return out.format(**values) if values else out
