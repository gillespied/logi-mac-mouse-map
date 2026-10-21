from logi_mouse_map.panel import panel_text


def test_panel_text_mentions_escape_and_timeout():
    headline, hint = panel_text(10.0)
    assert "shortcut" in headline.lower()
    assert "Esc" in hint
    assert "10s" in hint
