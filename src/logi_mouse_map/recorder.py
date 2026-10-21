"""Capture the next key combination the user presses."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import Quartz

from logi_mouse_map.keys import KEYCODES, MODIFIER_FLAGS, MODIFIER_ORDER, Combo

log = logging.getLogger(__name__)

KEYCODE_TO_NAME = {code: name for name, code in KEYCODES.items()}
ESCAPE_KEYCODE = KEYCODES["escape"]
TIMEOUT_S = 10.0


class Outcome(Enum):
    """How a recording attempt ended."""

    CAPTURED = "captured"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class RecordResult:
    """The outcome of a recording, with the captured combo when there is one."""

    outcome: Outcome
    combo: Combo | None = None


class ShortcutRecorder:
    """Swallows the next key-down and reports it as a Combo.

    Must be started from the main thread (it attaches to the main run loop).
    Requires Accessibility permission. Esc or a timeout cancels.
    """

    def __init__(self, on_done: Callable[[RecordResult], None]) -> None:
        self._on_done = on_done
        self._tap = None
        self._source = None
        self._timer = None

    def start(self) -> bool:
        """Begin recording. Returns False if the event tap could not be created."""
        mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask,
            self._callback,
            None,
        )
        if self._tap is None:
            return False
        self._source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        loop = Quartz.CFRunLoopGetMain()
        Quartz.CFRunLoopAddSource(loop, self._source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)

        self._timer = Quartz.CFRunLoopTimerCreateWithHandler(
            None,
            Quartz.CFAbsoluteTimeGetCurrent() + TIMEOUT_S,
            0,
            0,
            0,
            lambda _timer: self._finish(RecordResult(Outcome.TIMED_OUT)),
        )
        Quartz.CFRunLoopAddTimer(loop, self._timer, Quartz.kCFRunLoopCommonModes)
        return True

    def _callback(self, _proxy, event_type, event, _refcon):
        if event_type in (
            Quartz.kCGEventTapDisabledByTimeout,
            Quartz.kCGEventTapDisabledByUserInput,
        ):
            return event
        keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        if keycode == ESCAPE_KEYCODE:
            self._finish(RecordResult(Outcome.CANCELLED))
            return None
        key = KEYCODE_TO_NAME.get(keycode)
        if key is None:
            return None  # swallow keys we cannot represent
        flags = Quartz.CGEventGetFlags(event)
        # macOS sets the fn flag on arrow/function keys, so ignore it here.
        mods = tuple(m for m in MODIFIER_ORDER if m != "fn" and flags & MODIFIER_FLAGS[m])
        self._finish(RecordResult(Outcome.CAPTURED, Combo(key=key, modifiers=mods)))
        return None

    def _finish(self, result: RecordResult) -> None:
        if self._tap is None:
            return
        loop = Quartz.CFRunLoopGetMain()
        Quartz.CGEventTapEnable(self._tap, False)
        Quartz.CFRunLoopRemoveSource(loop, self._source, Quartz.kCFRunLoopCommonModes)
        Quartz.CFRunLoopTimerInvalidate(self._timer)
        self._tap = self._source = self._timer = None
        try:
            self._on_done(result)
        except Exception:
            log.exception("error handling recorded shortcut")
