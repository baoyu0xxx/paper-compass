from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest


def _touch_python(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env python\n", encoding="utf-8")


def test_runtime_state_reports_missing_when_managed_venv_absent(tmp_path):
    from paper_compass.runtime_env import runtime_state

    state = runtime_state(project_root=tmp_path, current_python=tmp_path / "python.exe")

    assert state.managed_exists is False
    assert state.managed_active is False
    assert state.status == "missing"
    assert any("managed runtime not initialized" in reason for reason in state.reasons)


def test_assert_managed_runtime_active_raises_clear_error_when_current_python_differs(tmp_path):
    from paper_compass.runtime_env import ManagedRuntimeError, assert_managed_runtime_active

    managed_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    _touch_python(managed_python)
    metadata_path = tmp_path / ".venv" / ".paper_compass_runtime.json"
    metadata_path.write_text(
        json.dumps(
            {
                "project_version": "1.3.0",
                "pyproject_sha256": "abc",
                "python_executable": str(managed_python),
                "python_version": "3.12.7",
                "extras": ["dev"],
                "install_mode": "editable",
                "installed_at": "2026-06-03T17:18:04Z",
            }
        ),
        encoding="utf-8",
    )

    wrong_python = tmp_path / "external" / "python.exe"
    _touch_python(wrong_python)

    with pytest.raises(ManagedRuntimeError) as excinfo:
        assert_managed_runtime_active(
            project_root=tmp_path,
            current_python=wrong_python,
            context="MCP server",
        )

    message = str(excinfo.value)
    assert "MCP server runtime error" in message
    assert str(wrong_python) in message
    assert str(managed_python) in message
    assert "bootstrap_runtime.py" in message


def test_ensure_managed_runtime_creates_venv_and_writes_metadata(tmp_path, monkeypatch):
    from paper_compass.runtime_env import ensure_managed_runtime

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "paper-compass"\nversion = "1.3.0"\nrequires-python = ">=3.12"\n',
        encoding="utf-8",
    )

    bootstrap_python = tmp_path / "bootstrap" / "python.exe"
    _touch_python(bootstrap_python)

    calls: list[list[str]] = []
    managed_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    version_probe = "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"

    def fake_run(command, *args, **kwargs):
        command = [str(part) for part in command]
        calls.append(command)
        if command == [str(bootstrap_python), "-c", version_probe]:
            return mock.Mock(returncode=0, stdout="3.12.7\n", stderr="")
        if command[:3] == [str(bootstrap_python), "-m", "venv"]:
            _touch_python(managed_python)
            return mock.Mock(returncode=0, stdout="", stderr="")
        if command == [str(managed_python), "-c", version_probe]:
            return mock.Mock(returncode=0, stdout="3.12.7\n", stderr="")
        if command[:4] == [str(managed_python), "-m", "pip", "install"]:
            return mock.Mock(returncode=0, stdout="ok\n", stderr="")
        raise AssertionError(f"unexpected subprocess call: {command}")

    monkeypatch.setattr("paper_compass.runtime_env.subprocess.run", fake_run)

    state = ensure_managed_runtime(project_root=tmp_path, bootstrap_python=bootstrap_python, with_dev=True)

    assert state.managed_exists is True
    assert state.status == "active"
    metadata = json.loads((tmp_path / ".venv" / ".paper_compass_runtime.json").read_text(encoding="utf-8"))
    assert metadata["project_version"] == "1.3.0"
    assert metadata["extras"] == ["dev"]
    assert any(command[:3] == [str(bootstrap_python), "-m", "venv"] for command in calls)
    assert any(command[-1] == ".[dev]" for command in calls if len(command) >= 5)
