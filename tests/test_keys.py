import pytest

from logi_mouse_map.keys import ShortcutError, parse_combo


def test_parse_orders_modifiers_and_resolves_aliases():
    combo = parse_combo("Command+Shift+Option+4")
    assert combo.modifiers == ("alt", "shift", "cmd")
    assert combo.key == "4"
    assert str(combo) == "alt+shift+cmd+4"


def test_parse_key_alias():
    assert parse_combo("cmd+esc").key == "escape"


def test_display_uses_symbols():
    assert parse_combo("ctrl+shift+right").display() == "⌃⇧→"


@pytest.mark.parametrize("text", ["", "cmd+", "cmd+nonsense", "hyper+a", "cmd++"])
def test_parse_rejects_invalid(text):
    with pytest.raises(ShortcutError):
        parse_combo(text)
