import plistlib
from pathlib import Path

from paper_compass import watch_autostart


def config(tmp_path):
    return {"runtime_root": str(tmp_path), "python": "C:/Program Files/Python/python.exe", "project_root": str(tmp_path), "config_path": str(tmp_path / "中文 path" / "watch_config.json")}


def test_native_definitions_keep_absolute_argv_without_secrets(tmp_path):
    data = config(tmp_path)
    win = watch_autostart.windows_definition(data)
    assert win["name"] == watch_autostart.service_name(tmp_path)
    assert '--managed' in win["command"]
    assert '"C:/Program Files/Python/python.exe"' in win["command"]
    mac = plistlib.loads(watch_autostart.macos_definition(data))
    assert mac["ProgramArguments"] == watch_autostart.launch_args(data)
    assert mac["KeepAlive"] == {"SuccessfulExit": False}
    unit = watch_autostart.linux_definition(data)
    assert "WantedBy=default.target" in unit
    assert "Restart=on-failure" in unit
    assert '"C:/Program Files/Python/python.exe"' in unit
    assert "API_KEY" not in unit


def test_native_name_stable_and_different_roots_distinct(tmp_path):
    assert watch_autostart.service_name(tmp_path) == watch_autostart.service_name(tmp_path / ".")
    assert watch_autostart.service_name(tmp_path) != watch_autostart.service_name(tmp_path / "other")


def test_inspection_exposes_native_failures_without_mutations(tmp_path, monkeypatch):
    monkeypatch.setattr(watch_autostart.sys, "platform", "win32")
    import sys
    from types import SimpleNamespace
    def fail(*args):
        raise PermissionError("access denied")
    monkeypatch.setitem(sys.modules, "winreg", SimpleNamespace(HKEY_CURRENT_USER=1, OpenKey=fail))
    assert watch_autostart.inspect(config(tmp_path))["error"] == "access denied"
    assert list(tmp_path.iterdir()) == []


def test_registry_lifecycle_is_user_scoped_and_rolls_back_failed_launch(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    import pytest

    data = config(tmp_path)
    python = tmp_path / "python.exe"
    python.touch()
    (tmp_path / "pythonw.exe").touch()
    data["python"] = str(python)
    values = {}
    key = MagicMock()
    key.__enter__.return_value = key
    def query(handle, name):
        if name not in values:
            raise FileNotFoundError(name)
        return values[name], 1
    registry = SimpleNamespace(
        HKEY_CURRENT_USER=123, KEY_SET_VALUE=2, REG_SZ=1,
        CreateKeyEx=MagicMock(return_value=key), OpenKey=MagicMock(return_value=key),
        SetValueEx=lambda handle, name, reserved, kind, value: values.update({name: value}),
        QueryValueEx=query, DeleteValue=lambda handle, name: values.pop(name),
    )
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(watch_autostart.sys, "platform", "win32")
    launch = MagicMock()
    monkeypatch.setattr(watch_autostart.subprocess, "Popen", launch)
    monkeypatch.setattr(watch_autostart.subprocess, "DETACHED_PROCESS", 8, raising=False)
    monkeypatch.setattr(watch_autostart.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)
    watch_autostart.enable(data)
    registry.CreateKeyEx.assert_called_once_with(123, watch_autostart.RUN_KEY, 0, 2)
    assert "pythonw.exe" in launch.call_args.args[0]
    assert watch_autostart.inspect(data)["registered"]
    watch_autostart.disable(data)
    assert not watch_autostart.inspect(data)["registered"]
    launch.side_effect = OSError("cannot launch")
    with pytest.raises(OSError, match="cannot launch"):
        watch_autostart.enable(data)
    assert not values
