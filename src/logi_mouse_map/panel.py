"""A small floating prompt shown while a shortcut is being recorded."""

from __future__ import annotations

from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSColor,
    NSFont,
    NSMakeRect,
    NSPanel,
    NSScreen,
    NSStatusWindowLevel,
    NSTextAlignmentCenter,
    NSTextField,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)

PANEL_WIDTH = 340
PANEL_HEIGHT = 96
CORNER_RADIUS = 14


def panel_text(timeout_s: float) -> tuple[str, str]:
    """Return the (headline, hint) lines shown in the recording prompt."""
    return "Press your shortcut", f"Esc to cancel · times out in {timeout_s:g}s"


def _label(text: str, y: float, size: float, bold: bool, alpha: float) -> NSTextField:
    field = NSTextField.labelWithString_(text)
    field.setFrame_(NSMakeRect(0, y, PANEL_WIDTH, size + 10))
    field.setAlignment_(NSTextAlignmentCenter)
    weight = NSFont.boldSystemFontOfSize_ if bold else NSFont.systemFontOfSize_
    field.setFont_(weight(size))
    field.setTextColor_(NSColor.colorWithWhite_alpha_(1.0, alpha))
    return field


class RecordingPanel:
    """Borderless always-on-top HUD, centred on the main screen."""

    def __init__(self, timeout_s: float) -> None:
        headline, hint = panel_text(timeout_s)
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        self._panel.setLevel_(NSStatusWindowLevel)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(NSColor.clearColor())
        self._panel.setHasShadow_(True)
        self._panel.setReleasedWhenClosed_(False)

        content = self._panel.contentView()
        content.setWantsLayer_(True)
        layer = content.layer()
        layer.setCornerRadius_(CORNER_RADIUS)
        layer.setBackgroundColor_(NSColor.colorWithWhite_alpha_(0.12, 0.92).CGColor())
        content.addSubview_(_label(headline, 48, 20, True, 1.0))
        content.addSubview_(_label(hint, 24, 12, False, 0.65))

    def show(self) -> None:
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        screen = NSScreen.mainScreen().frame()
        self._panel.setFrameOrigin_(
            (
                screen.origin.x + (screen.size.width - PANEL_WIDTH) / 2,
                screen.origin.y + (screen.size.height - PANEL_HEIGHT) / 2,
            )
        )
        self._panel.orderFrontRegardless()

    def close(self) -> None:
        self._panel.orderOut_(None)
