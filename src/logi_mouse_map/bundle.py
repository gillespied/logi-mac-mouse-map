"""Build a small .app bundle so macOS privacy permissions have a stable identity.

Input Monitoring and Accessibility are granted per code identity. Granting them to the
bare Python interpreter breaks whenever uv updates Python, so instead the LaunchAgent
runs a tiny native launcher inside this bundle. The launcher starts the real program as
a child process (it does not exec), so the child's requests are credited to the app.
"""

from __future__ import annotations

import plistlib
import subprocess
import tempfile
from pathlib import Path

BUNDLE_ID = "com.gillespied.logi-mouse-map"
APP_NAME = "Logi Mouse Map"
APP_PATH = Path.home() / "Applications" / f"{APP_NAME}.app"
LAUNCHER_NAME = "logi-mouse-map-launcher"

LAUNCHER_SOURCE = r"""
#include <signal.h>
#include <stdio.h>
#include <sys/wait.h>
#include <unistd.h>

static pid_t child = 0;

static void forward(int sig) {
    if (child > 0) kill(child, sig);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s program [args...]\n", argv[0]);
        return 2;
    }
    signal(SIGTERM, forward);
    signal(SIGINT, forward);
    signal(SIGHUP, forward);
    child = fork();
    if (child < 0) {
        perror("fork");
        return 1;
    }
    if (child == 0) {
        execv(argv[1], argv + 1);
        perror("execv");
        _exit(127);
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
    }
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    return 128 + (WIFSIGNALED(status) ? WTERMSIG(status) : 0);
}
"""


class BundleError(Exception):
    """Raised when the app bundle cannot be built."""


def build_info_plist() -> dict:
    """Return the bundle's Info.plist contents."""
    return {
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": LAUNCHER_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1",
        "CFBundleShortVersionString": "1.0",
        "LSUIElement": True,
    }


def launcher_path(app_path: Path = APP_PATH) -> Path:
    """Path of the launcher executable inside the bundle."""
    return app_path / "Contents" / "MacOS" / LAUNCHER_NAME


def build_bundle(app_path: Path = APP_PATH) -> Path:
    """Create or update the bundle, returning the launcher path.

    The launcher is only recompiled when missing or when its source changed, because
    a new binary hash makes macOS ask for the permissions again.
    """
    launcher = launcher_path(app_path)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    plist = app_path / "Contents" / "Info.plist"
    plist.write_bytes(plistlib.dumps(build_info_plist()))

    source_marker = app_path / "Contents" / "Resources" / "launcher-source.c"
    source_marker.parent.mkdir(parents=True, exist_ok=True)
    stale = not source_marker.exists() or source_marker.read_text() != LAUNCHER_SOURCE
    if not launcher.exists() or stale:
        _compile(launcher)
        source_marker.write_text(LAUNCHER_SOURCE)
        _sign(app_path)
    return launcher


def remove_bundle(app_path: Path = APP_PATH) -> None:
    """Delete the bundle if present."""
    import shutil

    shutil.rmtree(app_path, ignore_errors=True)


def _compile(output: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "launcher.c"
        source.write_text(LAUNCHER_SOURCE)
        _run(["clang", "-O2", "-o", str(output), str(source)], "compile the launcher")


def _sign(app_path: Path) -> None:
    _run(["codesign", "--force", "--sign", "-", str(app_path)], "sign the app bundle")


def _run(cmd: list[str], what: str) -> None:
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise BundleError(
            f"Cannot {what}: {cmd[0]} not found. Run 'xcode-select --install'."
        ) from exc
    if result.returncode != 0:
        raise BundleError(f"Cannot {what}: {result.stderr.strip()}")
