import pytest

from yarilo.hotkeys import MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, parse_hotkey


def test_arrows_with_modifiers():
    assert parse_hotkey("ctrl+alt+up") == (MOD_CONTROL | MOD_ALT, 0x26)
    assert parse_hotkey("Ctrl + Alt + Down") == (MOD_CONTROL | MOD_ALT, 0x28)


def test_letters_digits_and_function_keys():
    assert parse_hotkey("win+shift+b") == (MOD_WIN | MOD_SHIFT, ord("B"))
    assert parse_hotkey("ctrl+9") == (MOD_CONTROL, ord("9"))
    assert parse_hotkey("ctrl+f11") == (MOD_CONTROL, 0x7A)


def test_plus_minus_and_numpad():
    assert parse_hotkey("ctrl+alt+plus") == (MOD_CONTROL | MOD_ALT, 0xBB)
    assert parse_hotkey("ctrl+alt+minus") == (MOD_CONTROL | MOD_ALT, 0xBD)
    assert parse_hotkey("ctrl+num+") == (MOD_CONTROL, 0x6B)
    assert parse_hotkey("ctrl+num-") == (MOD_CONTROL, 0x6D)


def test_empty_means_off():
    assert parse_hotkey("") is None
    assert parse_hotkey("   ") is None


@pytest.mark.parametrize("bad", ["ctrl+", "ctrl+alt", "hyper+up", "ctrl+up+down", "up"])
def test_bad_hotkeys(bad):
    with pytest.raises(ValueError):
        parse_hotkey(bad)
