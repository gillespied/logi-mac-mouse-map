import plistlib
from pathlib import Path

import pytest

from logi_mouse_map import launchagent


def test_build_plist_runs_executable_and_keeps_alive_on_crash_only():
    plist = launchagent.build_plist(Path("/x/bin/logi-mouse-map"), Path("/tmp/log"))
    assert plist["ProgramArguments"] == ["/x/bin/logi-mouse-map", "run"]
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] == {"SuccessfulExit": False}
    assert plist["StandardOutPath"] == "/tmp/log"
    plistlib.dumps(plist)  # serialisable


def test_write_and_remove_plist(tmp_path, monkeypatch):
    monkeypatch.setattr(launchagent, "LOG_PATH", tmp_path / "logs" / "app.log")
    exe = tmp_path / "logi-mouse-map"
    exe.touch()
    path = tmp_path / "agents" / "x.plist"
    launchagent.write_plist(path, exe)
    assert launchagent.is_installed(path)
    assert plistlib.loads(path.read_bytes())["Label"] == launchagent.LABEL
    launchagent.remove_plist(path)
    assert not launchagent.is_installed(path)
    launchagent.remove_plist(path)  # idempotent


def test_write_plist_requires_executable(tmp_path):
    with pytest.raises(launchagent.LaunchAgentError):
        launchagent.write_plist(tmp_path / "x.plist", tmp_path / "missing")
