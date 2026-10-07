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
