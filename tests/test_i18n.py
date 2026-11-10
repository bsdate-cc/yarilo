import re
from pathlib import Path

from yarilo import i18n
from yarilo.i18n import EN, _, pick_language

SOURCES = Path(i18n.__file__).parent
SHOWN = re.compile(r'\b_\("((?:[^"\\]|\\.)*)"[,)]')   # _("text") and _("text {n}", n=...)


def test_every_shown_text_has_english():
    found = set()
    for f in SOURCES.glob("*.py"):
        found |= set(SHOWN.findall(f.read_text(encoding="utf-8")))
    assert "Монитор {n}" in found          # the pattern also sees texts with values
    missing = sorted(t for t in found if t not in EN)
    assert missing == []


def test_switching_language():
    i18n.set_language("en")
    assert _("Выход") == "Quit"
    assert _("Монитор {n}", n=2) == "Monitor 2"
    i18n.set_language("ru")
    assert _("Выход") == "Выход"
    assert _("Монитор {n}", n=2) == "Монитор 2"


def test_pick_language_from_windows():
    assert pick_language(0x0419, 0x0409) == "ru"     # Russian Windows
    assert pick_language(0x0409, 0x0419) == "ru"     # English Windows, Russian formats
    assert pick_language(0x0409, 0x0409) == "en"
