# Handoff notes

Context for picking this project up later. Delete this file once the work is merged and
anything useful has moved into the README.

## What this is

A macOS status bar app, in Python, that maps the thumb ("gesture") button on a Logitech
MX Master 2S to a keyboard shortcut chosen by the user. Personal project, plain `uv`,
repo `gillespied/logi-mac-mouse-map`. Hardware here: MX Master 2S on a Unifying receiver
(`046d:c52b`), mouse at receiver slot 3.

## How it works

- `hidpp.py`: HID++ 2.0 over the receiver's vendor interface (usage page `0xFF00`, usage
  `0x0002`). Finds feature `REPROG_CONTROLS_V4` (`0x1B04`), diverts control ID `0x00C3`,
  and turns the notifications into press/release. Re-applies the divert on reconnect and
  every 60s. Scans receiver slots 1-6 and Bluetooth (`0xFF`); Bluetooth is untested.
- `keys.py`: parses `cmd+shift+4` style strings and posts them with Quartz.
- `config.py`: `~/.config/logi-mac-mouse-map/config.toml` (`shortcut`, `enabled`).
  Hand edits need a restart.
- `app.py`: rumps status bar app. Presets, Record, Type, Enabled, Start at login, Quit.
- `recorder.py`: CGEventTap capture. Reports CAPTURED, CANCELLED or TIMED_OUT.
- `panel.py`: dark HUD panel used for the recording prompt and all confirmations.
- `launchagent.py`: LaunchAgent plist, `install`, `uninstall`, `restart`, `status`.
- `bundle.py`: builds `~/Applications/Logi Mouse Map.app` (see below).
- `instance.py`: `flock` single-instance lock at `~/.config/logi-mac-mouse-map/app.lock`.
- `cli.py`: `run` (default), `probe`, `send`, `install`, `uninstall`, `restart`, `status`.

## Decisions and why

- **Why not a normal mouse button:** the thumb button is only visible over HID++, so it
  has to be diverted. Logi Options is not installed and would conflict if it were.
- **No `rumps.notification`:** it needs a bundle ID and raises from a venv Python. All
  feedback uses `HudPanel` instead.
- **`NSTimer` for toasts, not `rumps.Timer`:** `rumps.Timer` fires immediately on start,
  which closed toasts at once. Use a one-shot `NSTimer`.
- **The app bundle:** privacy permissions attach to code identity. Granting them to the
  bare uv Python breaks when uv updates Python, and the file picker will not select it.
  So `install` builds a signed `.app` with a small C launcher. The launcher forks and
  waits (it does not `exec`) so the Python child is credited to the app. Verified working:
  after granting the app, the button fires.
- **Launcher is rebuilt only when its C source changes**, because a new binary hash
  makes macOS ask for permissions again. `uninstall` keeps the app for the same reason.
- **KeepAlive `SuccessfulExit=false`:** crash restarts, **Quit** (exit 0) stays quit.
- **Start at login menu toggle only adds or removes the plist.** It does not load or
  unload the job, because loading it would start a second copy. Takes effect next login.
- **Permissions only apply to processes started after the grant.** Run
  `logi-mouse-map restart` after granting or reinstalling.

## Branches and PRs

- `main`: v1 plus the recording feedback work (PR #1, merged).
- `launch-at-login`: PR #2 (draft), LaunchAgent and menu toggle. Based on `main`.
- `app-bundle`: PR #3 (draft), this branch. Stacked on `launch-at-login`: signed bundle,
  `restart`, single-instance lock, quieter logging, and this file.

To finish: merge #2, mark ready, retarget #3 to `main`, merge #3. The agent's permission
rules block `gh pr create` (non-draft), `gh pr ready` and `gh pr merge`, so these are
manual steps.

## Verified

- Button press and release reach Python via the probe; the shortcut fires (tested with
  `cmd+shift+4`).
- Recording works, with the HUD prompt and confirmation toast (checked by eye).
- LaunchAgent runs via the launcher; the button works after granting the app.
- Keep-alive: `pkill -9` and the process came back.
- Reinstall with `uv tool install . --reinstall` then `restart` kept the grant.
- 30 tests pass, `ruff check` clean.

## Not yet verified

- **Quit stays quit** (menu Quit should not respawn it; `status` still shows loaded).
- **Start at login toggle** (plist disappears and returns, pointing at the launcher).
- **A real logout/login or restart.**
- Mouse switched off/on, receiver unplugged, Mac sleep and wake.
- Holding the button should fire once, not repeat.
- Bluetooth connection (code path exists, never tested).
- The Type shortcut window icon (set directly; not seen after the last change).

## Known quirks

- Starting a copy by hand while the agent is installed takes the lock. After a
  `restart`, launchd takes a few seconds to bring the agent back; a manual copy started in
  that gap makes the agent fail with "already running" and launchd retries every ~10s.
  Do not run `logi-mouse-map` by hand while the agent is installed. Use `uninstall` first.
- `rumps` is old (0.4.0). The status icon uses SF Symbols via private `_nsapp` access.
- The "Type shortcut..." dialog is still a native `rumps.Window`, not a HUD panel.
- `ruff format --check` would reformat several files. Not applied to keep diffs small.
- The recorder uses an ANSI keycode map. Non-US layouts may map keys differently.

## Ideas for later

- Gestures: hold the button and move for different shortcuts.
- Reload the config file when it changes.
- Replace the Type shortcut dialog with a HUD-style text entry.
- Per-app shortcuts.
- Show a "mouse not found" state more reliably when the mouse is switched off but the
  receiver is still plugged in (unconfirmed what the icon does).

## Handy commands

```sh
uv run pytest && uv run ruff check .
uv tool install . --reinstall          # after code changes
logi-mouse-map restart                  # reload the agent
logi-mouse-map status
logi-mouse-map probe                    # needs the agent stopped (receiver is exclusive)
tail -f ~/Library/Logs/logi-mouse-map.log
launchctl print gui/$(id -u)/com.gillespied.logi-mouse-map
```
