from logi_mouse_map.app import describe_recording
from logi_mouse_map.keys import parse_combo
from logi_mouse_map.recorder import Outcome, RecordResult


def test_captured_mentions_shortcut():
    title, message = describe_recording(RecordResult(Outcome.CAPTURED, parse_combo("cmd+shift+4")))
    assert title == "Shortcut set"
    assert "⇧⌘4" in message
    assert "shift+cmd+4" in message


def test_timeout_says_unchanged():
    title, message = describe_recording(RecordResult(Outcome.TIMED_OUT))
    assert "timed out" in title.lower()
    assert "unchanged" in message


def test_escape_shows_no_alert():
    assert describe_recording(RecordResult(Outcome.CANCELLED)) is None
