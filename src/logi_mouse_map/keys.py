"""Parse keyboard shortcut strings and post them as macOS key events."""

from __future__ import annotations

import time
from dataclasses import dataclass

import Quartz

MODIFIER_FLAGS = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "fn": Quartz.kCGEventFlagMaskSecondaryFn,
}

MODIFIER_ALIASES = {
    "command": "cmd",
    "super": "cmd",
    "meta": "cmd",
    "shft": "shift",
    "option": "alt",
    "opt": "alt",
    "control": "ctrl",
}

# Modifier key codes, pressed explicitly so apps that watch flagsChanged see them.
MODIFIER_KEYCODES = {"cmd": 55, "shift": 56, "alt": 58, "ctrl": 59, "fn": 63}

# ANSI layout virtual key codes.
KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26,
    "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
    "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44,
    "n": 45, "m": 46, ".": 47, "`": 50,
    "return": 36, "tab": 48, "space": 49, "delete": 51, "escape": 53,
    "forwarddelete": 117, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111, "f13": 105, "f14": 107, "f15": 113,
    "f16": 106, "f17": 64, "f18": 79, "f19": 80, "f20": 90,
}  # fmt: skip

KEY_ALIASES = {
    "enter": "return",
    "esc": "escape",
    "backspace": "delete",
    "del": "forwarddelete",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "pgdown": "pagedown",
    "spacebar": "space",
}

KEY_DISPLAY = {
    "return": "Return", "tab": "Tab", "space": "Space", "delete": "Delete",
    "escape": "Esc", "forwarddelete": "Fwd Delete", "home": "Home", "end": "End",
    "pageup": "Page Up", "pagedown": "Page Down", "left": "←", "right": "→",
    "down": "↓", "up": "↑",
}  # fmt: skip

MODIFIER_SYMBOLS = {"ctrl": "⌃", "alt": "⌥", "shift": "⇧", "cmd": "⌘", "fn": "fn "}
MODIFIER_ORDER = ["ctrl", "alt", "shift", "cmd", "fn"]

KEY_TAP_DELAY_S = 0.01


class ShortcutError(ValueError):
    """Raised when a shortcut string cannot be parsed."""


@dataclass(frozen=True)
class Combo:
    """A key plus zero or more modifiers."""

    key: str
    modifiers: tuple[str, ...] = ()

    @property
    def keycode(self) -> int:
        return KEYCODES[self.key]

    def __str__(self) -> str:
        return "+".join([*self.modifiers, self.key])

    def display(self) -> str:
        """Human-friendly form such as '⌃⇧→'."""
        mods = "".join(MODIFIER_SYMBOLS[m] for m in self.modifiers)
        return mods + KEY_DISPLAY.get(self.key, self.key.upper())


def parse_combo(text: str) -> Combo:
    """Parse a string like 'cmd+shift+4' into a Combo."""
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if text.strip().endswith("++"):  # literal '+' key is not on the ANSI map
        raise ShortcutError("'+' cannot be used as the key; use '=' with shift")
    if not parts:
        raise ShortcutError("empty shortcut")

    *raw_mods, raw_key = parts
    key = KEY_ALIASES.get(raw_key, raw_key)
    if key not in KEYCODES:
        raise ShortcutError(f"unknown key: {raw_key!r}")

    mods = set()
    for raw in raw_mods:
        mod = MODIFIER_ALIASES.get(raw, raw)
        if mod not in MODIFIER_FLAGS:
            raise ShortcutError(f"unknown modifier: {raw!r}")
        mods.add(mod)
    ordered = tuple(m for m in MODIFIER_ORDER if m in mods)
    return Combo(key=key, modifiers=ordered)


def send_combo(combo: Combo) -> None:
    """Post the combo as key down/up events to the system."""
    flags = 0
    for mod in combo.modifiers:
        flags |= MODIFIER_FLAGS[mod]
        _post(MODIFIER_KEYCODES[mod], True, flags)

    _post(combo.keycode, True, flags)
    time.sleep(KEY_TAP_DELAY_S)
    _post(combo.keycode, False, flags)

    for mod in reversed(combo.modifiers):
        flags &= ~MODIFIER_FLAGS[mod]
        _post(MODIFIER_KEYCODES[mod], False, flags)


def _post(keycode: int, down: bool, flags: int) -> None:
    event = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
    Quartz.CGEventSetFlags(event, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
