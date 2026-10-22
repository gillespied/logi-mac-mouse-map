"""Install the app as a macOS LaunchAgent so it starts at login and is kept alive."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from logi_mouse_map import bundle

LABEL = "com.gillespied.logi-mouse-map"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_PATH = Path.home() / "Library" / "Logs" / "logi-mouse-map.log"
EXECUTABLE_NAME = "logi-mouse-map"


class LaunchAgentError(Exception):
    """Raised when the LaunchAgent cannot be installed or removed."""


def current_executable() -> Path:
    """Return the console script that sits next to the running Python interpreter."""
    return Path(sys.executable).parent / EXECUTABLE_NAME


def build_plist(executable: Path, log_path: Path = LOG_PATH, launcher: Path | None = None) -> dict:
    """Build the LaunchAgent definition.

    When a launcher is given it is run first and starts `executable` as a child, so
    privacy permissions attach to the launcher's app bundle.

    KeepAlive only restarts after a non-zero exit, so choosing Quit from the menu
    (exit code 0) stays quit until the next login.
    """
    return {
        "Label": LABEL,
        "ProgramArguments": (
            [str(launcher), str(executable), "run"] if launcher else [str(executable), "run"]
        ),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ProcessType": "Interactive",
        "LimitLoadToSessionType": "Aqua",
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }


def is_installed(path: Path = PLIST_PATH) -> bool:
    """Whether the LaunchAgent plist exists."""
    return path.exists()


def is_loaded() -> bool:
    """Whether launchd currently has the job loaded."""
    result = _launchctl("print", _service_target(), check=False)
    return result.returncode == 0


def write_plist(path: Path = PLIST_PATH, executable: Path | None = None) -> Path:
    """Write the plist so the app starts at the next login. Does not start it now."""
    executable = executable or current_executable()
    if not executable.exists():
        raise LaunchAgentError(
            f"{executable} not found. Install the tool first with 'uv tool install .'"
        )
    try:
        launcher = bundle.build_bundle()
    except bundle.BundleError as exc:
        raise LaunchAgentError(str(exc)) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(build_plist(executable, launcher=launcher)))
    return executable


def remove_plist(path: Path = PLIST_PATH) -> None:
    """Delete the plist so the app no longer starts at login."""
    path.unlink(missing_ok=True)


def install() -> Path:
    """Write the plist and load it into launchd now, replacing any loaded copy."""
    executable = write_plist()
    if is_loaded():
        _launchctl("bootout", _service_target())
    _launchctl("bootstrap", _domain(), str(PLIST_PATH))
    return executable


def restart() -> None:
    """Restart the loaded job, for example to pick up new permissions or a reinstall."""
    if not is_loaded():
        raise LaunchAgentError("not loaded; run 'logi-mouse-map install' first")
    _launchctl("kickstart", "-k", _service_target())


def uninstall() -> None:
    """Stop the loaded job, if any, and delete the plist.

    The app bundle is kept so its privacy permissions survive a reinstall.
    """
    if is_loaded():
        _launchctl("bootout", _service_target())
    remove_plist()


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _service_target() -> str:
    return f"{_domain()}/{LABEL}"


def _launchctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["launchctl", *args], check=False, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise LaunchAgentError(f"launchctl {args[0]} failed: {result.stderr.strip()}")
    return result
