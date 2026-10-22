import plistlib
import subprocess

import pytest

from logi_mouse_map import bundle, launchagent


def test_info_plist_identity_and_agent_mode():
    info = bundle.build_info_plist()
    assert info["CFBundleIdentifier"] == bundle.BUNDLE_ID
    assert info["CFBundleExecutable"] == bundle.LAUNCHER_NAME
    assert info["LSUIElement"] is True
    plistlib.dumps(info)


def test_launchagent_runs_launcher_then_tool(tmp_path):
    plist = launchagent.build_plist(
        tmp_path / "tool", tmp_path / "log", launcher=tmp_path / "launcher"
    )
    assert plist["ProgramArguments"] == [str(tmp_path / "launcher"), str(tmp_path / "tool"), "run"]


@pytest.mark.skipif(not bundle.APP_PATH.parent.exists(), reason="needs macOS toolchain")
def test_build_bundle_is_signed_and_idempotent(tmp_path):
    app = tmp_path / "T.app"
    launcher = bundle.build_bundle(app)
    first = launcher.read_bytes()
    bundle.build_bundle(app)
    assert launcher.read_bytes() == first  # not recompiled
    verify = subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=False)
    assert verify.returncode == 0


def test_launcher_passes_exit_code(tmp_path):
    launcher = bundle.build_bundle(tmp_path / "T.app")
    result = subprocess.run([str(launcher), "/bin/sh", "-c", "exit 3"], check=False)
    assert result.returncode == 3
