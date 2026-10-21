# logi-mouse-map

A small macOS status bar app that maps the **thumb button** on a Logitech MX Master
mouse (tested design: MX Master 2S via Unifying receiver) to a keyboard shortcut of
your choice. No Logi Options needed.

## Why it works

The thumb ("gesture") button is not reported to macOS as a normal mouse click. It is
only visible over Logitech's HID++ protocol (feature `REPROG_CONTROLS_V4`, control ID
`0x00C3`). This app "diverts" that button so the mouse sends it as a HID++ notification,
then posts the configured shortcut as a keyboard event.

## Setup

```sh
uv sync
uv run logi-mouse-map
```

A mouse icon appears in the menu bar. Filled means the mouse is connected, outlined
means it was not found, and a pause icon means the mapping is disabled.

### Permissions

macOS will prompt for these for the app that launched Python (Terminal, iTerm, VS Code…).
Grant them in **System Settings → Privacy & Security**:

- **Input Monitoring**: to read from the Logitech receiver.
- **Accessibility**: to post keyboard events, and to record shortcuts.

Restart the terminal after granting.

> Quit Logi Options / Options+ first if installed. They also divert the button and
> will conflict.

## Choosing the shortcut

From the menu bar icon:

- **Presets**: Mission Control (default, `ctrl+up`), Spotlight, App Switcher, and more.
- **Record shortcut…**: press the combination you want (Esc cancels, 10s timeout).
- **Type shortcut…**: type a combo such as `cmd+shift+4` or `ctrl+alt+left`.
- **Enabled**: temporarily turn the mapping off.

The choice is saved to `~/.config/logi-mac-mouse-map/config.toml`:

```toml
shortcut = "ctrl+up"
enabled = true
```

Modifiers: `cmd`, `shift`, `alt` (`option`), `ctrl`, `fn`. Keys: letters, digits,
punctuation, `space`, `return`, `tab`, `escape`, `delete`, arrows, `home`, `end`,
`pageup`, `pagedown`, and `f1`–`f20`. Edits to the file take effect on restart.

Note that `ctrl+up` only opens Mission Control if that shortcut is enabled in
System Settings → Keyboard → Keyboard Shortcuts → Mission Control.

## Command line

```sh
uv run logi-mouse-map probe          # print thumb button press/release events
uv run logi-mouse-map send ctrl+up --delay 2   # test sending a shortcut
uv run logi-mouse-map -v run         # run with debug logging
```

## Troubleshooting

- **"Mouse: not found"**: check the receiver is plugged in and Input Monitoring is
  granted. Run `probe -v` to see which receiver slots were tried.
- **Button does nothing**: run `probe`. If presses print but the shortcut does not fire,
  grant Accessibility. If nothing prints, another app may be diverting the button.
- **Stops working after the mouse sleeps**: the divert is re-applied when the receiver
  reports a reconnect and every 60 seconds as a safety net.
- Bluetooth connections are supported in code (device index `0xFF`) but untested.

## Development

```sh
uv run pytest
uv run ruff check .
```

## Not yet done (v2)

- Launch at login and keep-alive via a LaunchAgent.
- Gestures (hold the button and move).
