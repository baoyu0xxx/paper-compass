"""Native per-user login services. No credentials are stored in definitions."""
from __future__ import annotations

import hashlib
import os
import plistlib
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def service_name(runtime_root: str | Path) -> str:
    identity = os.path.normcase(str(Path(runtime_root).expanduser().resolve()))
    return "paper-compass-watch-" + hashlib.sha256(identity.encode()).hexdigest()[:12]


def launch_args(config: dict) -> list[str]:
    return [config["python"], "-u", "-m", "paper_compass", "watch", "--managed", "--watch-config", config["config_path"]]


def _run(args: list[str], *, check=True) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except OSError as exc:
        raise RuntimeError(f"Cannot invoke {args[0]}: {exc}") from exc
    if check and result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result


def windows_startup_path(config: dict) -> Path:
    folder = Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return folder / (service_name(config["runtime_root"]) + ".cmd")


def _startup_script(config: dict) -> str:
    args = launch_args(config)
    windowless = Path(args[0]).with_name("pythonw.exe")
    if windowless.is_file():
        args[0] = str(windowless)
    if any(any(char in arg for char in '\r\n"') for arg in args):
        raise ValueError("Startup paths contain unsupported command characters")
    command = " ".join('"' + arg.replace("%", "%%") + '"' for arg in args)
    return f'@echo off\nsetlocal DisableDelayedExpansion\nstart "paper-compass watcher" /b {command}\n'


def windows_definition(config: dict) -> dict:
    args = launch_args(config)
    windowless = Path(args[0]).with_name("pythonw.exe")
    if windowless.is_file():
        args[0] = str(windowless)
    return {"name": service_name(config["runtime_root"]), "command": subprocess.list2cmdline(args)}


def _reg_add(name: str, command: str) -> None:
    _run(["reg.exe", "ADD", "HKCU\\" + RUN_KEY, "/v", name, "/t", "REG_SZ", "/d", command, "/f"])


def _reg_delete(name: str) -> None:
    _run(["reg.exe", "DELETE", "HKCU\\" + RUN_KEY, "/v", name, "/f"], check=False)


def _reg_query(name: str) -> str | None:
    response = _run(["reg.exe", "QUERY", "HKCU\\" + RUN_KEY, "/v", name], check=False)
    if response.returncode:
        return None
    for line in response.stdout.splitlines():
        if name in line and "REG_SZ" in line:
            return line.split("REG_SZ", 1)[1].strip()
    return None


    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$").replace("\n", "\\n").replace("\r", "\\r") + '"'


def _unit_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$").replace("\n", "\\n").replace("\r", "\\r") + '"'


def linux_definition(config: dict) -> str:
    command = " ".join(_unit_quote(arg) for arg in launch_args(config))
    return (
        "[Unit]\nDescription=Paper Compass automatic Zotero updates\n\n[Service]\nType=simple\n"
        f"ExecStart={command}\nWorkingDirectory={_unit_quote(config['project_root'])}\n"
        "Environment=PYTHONUTF8=1\nEnvironment=PYTHONIOENCODING=utf-8\n"
        "Restart=on-failure\nRestartSec=30\nKillMode=process\nTimeoutStopSec=infinity\n\n[Install]\nWantedBy=default.target\n"
    )


def macos_definition(config: dict) -> bytes:
    return plistlib.dumps({
        "Label": service_name(config["runtime_root"]), "ProgramArguments": launch_args(config),
        "WorkingDirectory": config["project_root"], "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 30,
        "EnvironmentVariables": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    })


def _definition_path(config: dict) -> Path:
    name = service_name(config["runtime_root"])
    if sys.platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / (name + ".plist")
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "systemd" / "user" / (name + ".service")


def enable(config: dict) -> None:
    if not Path(config["python"]).is_file() or not Path(config["project_root"]).is_dir():
        raise RuntimeError("Watcher interpreter or working directory no longer exists")
    name = service_name(config["runtime_root"])
    if sys.platform == "win32":
        import winreg
        definition = windows_definition(config)
        if len(definition["command"]) > 260:
            raise RuntimeError("Windows Run command exceeds 260 characters; use shorter runtime paths")
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, definition["command"])
        except PermissionError:
            _reg_add(name, definition["command"])
        try:
            subprocess.Popen(
                definition["command"], cwd=config["project_root"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        except OSError:
            disable(config)
            raise
    elif sys.platform.startswith("linux"):
        _run(["systemctl", "--user", "show-environment"])
        path = _definition_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(linux_definition(config), encoding="utf-8")
        _run(["systemctl", "--user", "daemon-reload"])
        _run(["systemctl", "--user", "enable", name + ".service"])
        _run(["systemctl", "--user", "restart", name + ".service"])
    elif sys.platform == "darwin":
        domain = f"gui/{os.getuid()}"
        _run(["launchctl", "print", domain])
        if inspect(config)["registered"]:
            _run(["launchctl", "bootout", domain + "/" + name])
        path = _definition_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(macos_definition(config))
        _run(["launchctl", "bootstrap", domain, str(path)])
    else:
        raise RuntimeError(f"Login autostart is unsupported on {sys.platform}")


def disable(config: dict) -> None:
    name = service_name(config["runtime_root"])
    if sys.platform == "win32":
        import winreg
        windows_startup_path(config).unlink(missing_ok=True)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass
        except PermissionError:
            if _reg_query(name) is not None:
                _reg_delete(name)
    elif sys.platform.startswith("linux"):
        path = _definition_path(config)
        if path.exists():
            _run(["systemctl", "--user", "disable", name + ".service"])
            path.unlink()
            _run(["systemctl", "--user", "daemon-reload"])
    elif sys.platform == "darwin":

        if inspect(config)["registered"]:
            _run(["launchctl", "bootout", f"gui/{os.getuid()}/{name}"])
        _definition_path(config).unlink(missing_ok=True)
    else:
        raise RuntimeError(f"Login autostart is unsupported on {sys.platform}")


def inspect(config: dict) -> dict:
    result = {"platform": sys.platform, "name": service_name(config["runtime_root"]), "registered": False, "running": False, "error": ""}
    try:
        if sys.platform == "win32":
            import winreg
            result["manager"] = "registry-run"
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                    command, kind = winreg.QueryValueEx(key, result["name"])
                result["registered"] = kind == winreg.REG_SZ and command == windows_definition(config)["command"]
                if not result["registered"]:
                    result["error"] = "Startup command differs from configuration; re-enable autostart"
            except FileNotFoundError:
                pass
            except PermissionError as exc:
                command = _reg_query(result["name"])
                if command is not None:
                    result["registered"] = command == windows_definition(config)["command"]
                    if not result["registered"]:
                        result["error"] = "Startup command differs from configuration; re-enable autostart"
                elif not result["error"]:
                    result["error"] = str(exc)
            path = windows_startup_path(config)
            if path.is_file():
                result["manager"] = "startup-folder"
                result["registered"] = path.read_text(encoding="utf-8") == _startup_script(config)
                result["error"] = "" if result["registered"] else "Startup script differs from configuration; re-enable autostart"
        elif sys.platform.startswith("linux"):
            response = _run(["systemctl", "--user", "show", result["name"] + ".service", "--property=LoadState,ActiveState,UnitFileState"], check=False)
            values = dict(line.split("=", 1) for line in response.stdout.splitlines() if "=" in line)
            result.update(registered=values.get("UnitFileState") == "enabled", running=values.get("ActiveState") == "active")
            if response.returncode:
                result["error"] = response.stderr.strip()
        elif sys.platform == "darwin":
            response = _run(["launchctl", "print", f"gui/{os.getuid()}/{result['name']}"], check=False)
            result.update(registered=response.returncode == 0, running=response.returncode == 0 and "state = running" in response.stdout)
        else:
            result["error"] = f"Unsupported platform: {sys.platform}"
        if config.get("python") and not Path(config["python"]).is_file() and not result.get("error"):
            result["error"] = "Registered interpreter no longer exists; reinstall autostart"
    except (OSError, RuntimeError, ValueError) as exc:
        result["error"] = str(exc)
    return result
