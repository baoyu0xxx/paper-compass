from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from paper_compass import windows_integrity


def test_non_windows_process_does_not_change_permissions(monkeypatch, tmp_path):
    monkeypatch.setattr(windows_integrity.os, "name", "posix")
    windows_integrity.set_low_integrity_runtime_root(tmp_path)


def test_low_integrity_rejects_non_default_root(monkeypatch, tmp_path):
    monkeypatch.setattr(windows_integrity.os, "name", "nt")
    monkeypatch.setattr(windows_integrity, "is_low_integrity_process", lambda: True)
    with pytest.raises(RuntimeError, match="non-default runtime root"):
        windows_integrity.set_low_integrity_runtime_root(tmp_path)


def test_low_integrity_reports_medium_shell_repair(monkeypatch, tmp_path):
    root = Path.home() / ".paper-compass"
    monkeypatch.setattr(windows_integrity.os, "name", "nt")
    monkeypatch.setattr(windows_integrity, "is_low_integrity_process", lambda: True)
    monkeypatch.setattr(windows_integrity.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, b"", b"Access is denied"))
    with pytest.raises(RuntimeError, match="Medium Integrity shell") as exc:
        windows_integrity.set_low_integrity_runtime_root(root)
    assert "setintegritylevel" in str(exc.value)
    assert str(root) in str(exc.value)


def test_zone_helpers_are_noop_off_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(windows_integrity.os, "name", "posix")
    executable = tmp_path / "python.exe"
    executable.write_bytes(b"")
    assert windows_integrity.has_zone_mark(executable) is False
    assert windows_integrity.clear_zone_marks([executable]) == []
    assert windows_integrity.launcher_files(executable) == []


@pytest.mark.skipif(windows_integrity.os.name != "nt", reason="needs NTFS alternate data streams")
def test_clear_zone_marks_removes_the_mark(tmp_path):
    executable = tmp_path / "pythonw.exe"
    executable.write_bytes(b"")
    with open(str(executable) + ":Zone.Identifier", "w", encoding="utf-8") as stream:
        stream.write("[ZoneTransfer]\r\nZoneId=3\r\n")
    assert windows_integrity.has_zone_mark(executable) is True

    assert windows_integrity.clear_zone_marks([executable]) == []
    assert windows_integrity.has_zone_mark(executable) is False


def test_launcher_files_cover_a_virtual_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(windows_integrity.os, "name", "nt")
    venv = tmp_path / ".venv"
    scripts = venv / "Scripts"
    scripts.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = base\n", encoding="utf-8")
    for name in ("python.exe", "pythonw.exe", "paper-compass.exe"):
        (scripts / name).write_bytes(b"")

    files = windows_integrity.launcher_files(scripts / "python.exe")

    assert {path.name for path in files} == {"python.exe", "pythonw.exe", "paper-compass.exe"}


def test_launcher_files_outside_a_virtual_environment_stay_minimal(monkeypatch, tmp_path):
    monkeypatch.setattr(windows_integrity.os, "name", "nt")
    base = tmp_path / "base"
    base.mkdir()
    for name in ("python.exe", "pythonw.exe", "other-tool.exe"):
        (base / name).write_bytes(b"")

    files = windows_integrity.launcher_files(base / "python.exe")

    assert {path.name for path in files} == {"python.exe", "pythonw.exe"}
