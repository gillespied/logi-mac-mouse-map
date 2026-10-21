"""Command line entry point."""

from __future__ import annotations

import argparse
import logging
import sys
import time

from logi_mouse_map.launchagent import LaunchAgentError


def _probe() -> int:
    from logi_mouse_map.hidpp import ButtonListener

    listener = ButtonListener(
        on_press=lambda: print("thumb button: PRESS", flush=True),
        on_release=lambda: print("thumb button: release", flush=True),
        on_status=lambda ok: print(f"connected: {ok}", flush=True),
    )
    listener.start()
    print("Listening. Press the thumb button; Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()
    return 0


def _send(combo: str, delay: float) -> int:
    from logi_mouse_map.keys import parse_combo, send_combo

    parsed = parse_combo(combo)
    if delay:
        print(f"Sending in {delay:g}s...")
        time.sleep(delay)
    send_combo(parsed)
    return 0


def _install() -> int:
    from logi_mouse_map import bundle, launchagent

    executable = launchagent.install()
    print(f"Installed and started LaunchAgent {launchagent.LABEL}")
    print(f"  runs:  {executable} run")
    print(f"  plist: {launchagent.PLIST_PATH}")
    print(f"  log:   {launchagent.LOG_PATH}")
    print()
    print(f"  app:   {bundle.APP_PATH}")
    print()
    print("Grant Input Monitoring and Accessibility to the app in System Settings >")
    print("Privacy & Security (click '+', choose it from ~/Applications). Then run")
    print("'logi-mouse-map uninstall && logi-mouse-map install' to reload it.")
    return 0


def _uninstall() -> int:
    from logi_mouse_map import launchagent

    launchagent.uninstall()
    print("LaunchAgent removed.")
    return 0


def _status() -> int:
    from logi_mouse_map import launchagent

    print(f"plist installed: {launchagent.is_installed()} ({launchagent.PLIST_PATH})")
    print(f"loaded in launchd: {launchagent.is_loaded()}")
    return 0


def _run() -> int:
    from logi_mouse_map.app import run_app

    run_app()
    return 0


COMMANDS = {"install": _install, "uninstall": _uninstall, "status": _status}


def main() -> None:
    parser = argparse.ArgumentParser(prog="logi-mouse-map")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="start the status bar app (default)")
    sub.add_parser("probe", help="print thumb button events")
    sub.add_parser("install", help="start at login and keep alive (LaunchAgent)")
    sub.add_parser("uninstall", help="remove the LaunchAgent")
    sub.add_parser("status", help="show LaunchAgent state")
    send = sub.add_parser("send", help="send a keyboard shortcut, e.g. 'ctrl+up'")
    send.add_argument("combo")
    send.add_argument("--delay", type=float, default=0.0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    command = args.command or "run"
    if command == "probe":
        code = _probe()
    elif command in COMMANDS:
        try:
            code = COMMANDS[command]()
        except LaunchAgentError as exc:
            print(f"error: {exc}", file=sys.stderr)
            code = 1
    elif command == "send":
        code = _send(args.combo, args.delay)
    else:
        code = _run()
    sys.exit(code)
