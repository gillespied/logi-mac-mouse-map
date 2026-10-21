"""Status bar application."""

from __future__ import annotations

import logging
import threading

import rumps
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSImage,
    NSImageSymbolConfiguration,
)

from logi_mouse_map.config import Config, load_config, save_config
from logi_mouse_map.hidpp import ButtonListener
from logi_mouse_map.keys import Combo, ShortcutError, parse_combo, send_combo
from logi_mouse_map.panel import RecordingPanel
from logi_mouse_map.recorder import TIMEOUT_S, Outcome, RecordResult, ShortcutRecorder

log = logging.getLogger(__name__)

PRESETS: list[tuple[str, str]] = [
    ("Mission Control", "ctrl+up"),
    ("App Exposé", "ctrl+down"),
    ("Spotlight", "cmd+space"),
    ("App Switcher", "cmd+tab"),
    ("Close Window", "cmd+w"),
    ("Screenshot Selection", "cmd+shift+4"),
    ("Desktop Left", "ctrl+left"),
    ("Desktop Right", "ctrl+right"),
    ("Show Desktop", "f11"),
]

ICON_CONNECTED = "computermouse.fill"
ICON_DISCONNECTED = "computermouse"
ICON_DISABLED = "pause.circle"
ICON_RECORDING = "record.circle"
APP_NAME = "Logi Mouse Map"
UI_REFRESH_S = 1.0
RECORDING_TITLE = " Press keys…"
APP_ICON_SIZE = 128


def describe_recording(result: RecordResult) -> tuple[str, str] | None:
    """Return the (title, message) to show for a recording result, or None for no alert."""
    if result.outcome is Outcome.CAPTURED and result.combo is not None:
        combo = result.combo
        return "Shortcut set", f"The thumb button now sends {combo.display()}  ({combo})"
    if result.outcome is Outcome.TIMED_OUT:
        return "Recording timed out", "No key was pressed. The shortcut is unchanged."
    return None


def _symbol(name: str) -> NSImage | None:
    image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, APP_NAME)
    if image is not None:
        image.setTemplate_(True)
    return image


def _set_app_icon() -> None:
    """Use the mouse symbol as the app icon so alerts don't show a generic folder."""
    image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        ICON_CONNECTED, APP_NAME
    )
    if image is None:
        return
    config = NSImageSymbolConfiguration.configurationWithPointSize_weight_(APP_ICON_SIZE, 5)
    image = image.imageWithSymbolConfiguration_(config)
    image.setTemplate_(False)
    NSApplication.sharedApplication().setApplicationIconImage_(image)


class MouseMapApp(rumps.App):
    """Menu bar app that maps the thumb button to a keyboard shortcut."""

    def __init__(self) -> None:
        super().__init__(APP_NAME, title=None, quit_button=None)
        self.config: Config = load_config()
        self._combo = self._parse_or_default(self.config.shortcut)
        self._connected = False
        self._lock = threading.Lock()
        self._recorder: ShortcutRecorder | None = None
        self._recording = False
        self._panel: RecordingPanel | None = None

        self._status_item = rumps.MenuItem("Mouse: searching…")
        self._shortcut_item = rumps.MenuItem("")
        self._enabled_item = rumps.MenuItem("Enabled", callback=self._toggle_enabled)
        self._presets_menu = rumps.MenuItem("Presets")
        for label, combo in PRESETS:
            item = rumps.MenuItem(f"{label}  ({parse_combo(combo).display()})")
            item.set_callback(self._make_preset_callback(combo))
            self._presets_menu[item.title] = item
            item._combo_str = combo  # type: ignore[attr-defined]
        self.menu = [
            self._status_item,
            self._shortcut_item,
            None,
            self._presets_menu,
            rumps.MenuItem("Record shortcut…", callback=self._record),
            rumps.MenuItem("Type shortcut…", callback=self._type_custom),
            None,
            self._enabled_item,
            None,
            rumps.MenuItem("Quit", callback=self._quit),
        ]

        self._listener = ButtonListener(
            on_press=self._on_press,
            on_status=self._on_status,
        )
        self._refresh_timer = rumps.Timer(self._refresh, UI_REFRESH_S)
        self._refresh()

    @staticmethod
    def _parse_or_default(text: str) -> Combo:
        try:
            return parse_combo(text)
        except ShortcutError:
            log.warning("invalid shortcut %r in config; using default", text)
            return parse_combo(Config().shortcut)

    def run(self, **options) -> None:  # type: ignore[override]
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )
        _set_app_icon()
        self._listener.start()
        self._refresh_timer.start()
        super().run(**options)

    # --- listener callbacks (background thread) ---------------------------

    def _on_press(self) -> None:
        with self._lock:
            enabled = self.config.enabled
            combo = self._combo
        if enabled:
            send_combo(combo)

    def _on_status(self, connected: bool) -> None:
        with self._lock:
            self._connected = connected

    # --- UI (main thread) --------------------------------------------------

    def _refresh(self, _sender=None) -> None:
        with self._lock:
            connected = self._connected
            enabled = self.config.enabled
            combo = self._combo
            recording = self._recording

        self._status_item.title = "Mouse: connected" if connected else "Mouse: not found"
        if recording:
            self._shortcut_item.title = "Recording… press shortcut (Esc cancels)"
        else:
            self._shortcut_item.title = f"Shortcut: {combo.display()}  ({combo})"
        self._enabled_item.state = enabled
        for item in self._presets_menu.values():
            item.state = item._combo_str == str(combo)  # type: ignore[attr-defined]

        title = ""
        if recording:
            symbol = ICON_RECORDING
            title = RECORDING_TITLE
        elif not enabled:
            symbol = ICON_DISABLED
        else:
            symbol = ICON_CONNECTED if connected else ICON_DISCONNECTED
        self._set_icon(symbol, title)

    def _set_icon(self, symbol: str, title: str = "") -> None:
        if getattr(self, "_current_icon", None) == (symbol, title):
            return
        nsapp = getattr(self, "_nsapp", None)
        status_item = getattr(nsapp, "nsstatusitem", None)
        if status_item is None:
            return  # status bar not created yet; the refresh timer will retry
        button = status_item.button()
        image = _symbol(symbol)
        if image is None:
            button.setTitle_(title or "Mouse")
        else:
            button.setTitle_(title)
            button.setImage_(image)
        self._current_icon = (symbol, title)

    def _set_combo(self, combo: Combo) -> None:
        with self._lock:
            self._combo = combo
            self.config.shortcut = str(combo)
            save_config(self.config)
        self._refresh()

    def _make_preset_callback(self, combo_str: str):
        def callback(_sender) -> None:
            self._set_combo(parse_combo(combo_str))

        return callback

    def _toggle_enabled(self, _sender) -> None:
        with self._lock:
            self.config.enabled = not self.config.enabled
            save_config(self.config)
        self._refresh()

    def _type_custom(self, _sender) -> None:
        window = rumps.Window(
            message="Enter a shortcut such as cmd+shift+4 or ctrl+alt+left",
            title="Set shortcut",
            default_text=str(self._combo),
            ok="Save",
            cancel="Cancel",
            dimensions=(260, 24),
        )
        response = window.run()
        if not response.clicked:
            return
        try:
            self._set_combo(parse_combo(response.text))
        except ShortcutError as exc:
            rumps.alert("Invalid shortcut", str(exc))

    def _record(self, _sender) -> None:
        if self._recorder is not None:
            return
        recorder = ShortcutRecorder(self._on_recorded)
        if not recorder.start():
            rumps.alert(
                "Cannot record",
                "Grant Accessibility access to the app running this (e.g. your terminal) in "
                "System Settings → Privacy & Security, then restart it and try again.",
            )
            return
        self._recorder = recorder
        self._panel = RecordingPanel(TIMEOUT_S)
        self._panel.show()
        self._set_recording(True)

    def _on_recorded(self, result: RecordResult) -> None:
        self._recorder = None
        if self._panel is not None:
            self._panel.close()
            self._panel = None
        self._set_recording(False)
        if result.combo is not None:
            self._set_combo(result.combo)
        message = describe_recording(result)
        if message is not None:
            self._show_alert_soon(*message)

    def _show_alert_soon(self, title: str, message: str) -> None:
        """Show an alert on the next run-loop tick, outside the event tap callback."""

        def show(timer: rumps.Timer) -> None:
            timer.stop()
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            rumps.alert(title, message)

        self._alert_timer = rumps.Timer(show, 0.05)
        self._alert_timer.start()

    def _set_recording(self, recording: bool) -> None:
        with self._lock:
            self._recording = recording
        self._refresh()

    def _quit(self, _sender) -> None:
        self._listener.stop()
        rumps.quit_application()


def run_app() -> None:
    MouseMapApp().run()
