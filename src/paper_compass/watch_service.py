"""Confirmed watcher configuration and per-user managed lifecycle."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from paper_compass import watch_autostart
from paper_compass.env_utils import DEFAULT_ENV_PATH, PROJECT_ROOT


class WatchAlreadyRunning(RuntimeError):
    pass


def config_path(root: str | Path) -> Path:
    return Path(root).resolve() / "state" / "watch_config.json"


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_config(root: str | Path) -> dict:
    return read_json(config_path(root))


def confirm_source(db_path: str | Path, storage_path: str | Path) -> tuple[str, str]:
    db = Path(db_path).expanduser().resolve()
    storage = Path(storage_path).expanduser().resolve()
    if not db.is_file() or not storage.is_dir():
        raise ValueError("Zotero database and storage must already exist")
    try:
        with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=5) as connection:
            connection.execute("PRAGMA query_only=ON")
            if not connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'").fetchone():
                raise ValueError("The selected database is not a Zotero library (items table missing)")
    except sqlite3.Error as exc:
        raise ValueError(f"Cannot read Zotero database: {exc}") from exc
    return str(db), str(storage)


def save_choice(root: str | Path, *, enabled: bool, db_path: str, storage_path: str,
                env_path: str | Path | None = None) -> dict:
    root = Path(root).expanduser().resolve()
    data = {
        "version": 1, "runtime_root": str(root), "config_path": str(config_path(root)),
        "enabled": enabled, "decision": "accepted" if enabled else "declined",
        "db_path": db_path, "storage_path": storage_path,
        "python": sys.executable, "project_root": str(PROJECT_ROOT),
        "env_path": str(Path(env_path or os.environ.get("PAPER_COMPASS_ENV_PATH") or DEFAULT_ENV_PATH).resolve()),
        "debounce_seconds": 3.0, "reconcile_seconds": 600.0, "error": "",
    }
    write_json(config_path(root), data)
    return data


def _lock_file(root: str | Path) -> Path:
    return Path(root) / "state" / "watch.lock"


def _lock(stream, acquire: bool = True) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK if acquire else msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), (fcntl.LOCK_EX | fcntl.LOCK_NB) if acquire else fcntl.LOCK_UN)


@contextmanager
def instance_lock(root: str | Path):
    path = _lock_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if path.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        try:
            _lock(stream)
        except OSError as exc:
            raise WatchAlreadyRunning("A watcher is already running for this runtime root") from exc
        try:
            yield
        finally:
            _lock(stream, False)


def is_running(root: str | Path) -> bool:
    path = _lock_file(root)
    if not path.exists():
        return False
    try:
        with path.open("r+b") as stream:
            try:
                _lock(stream)
            except OSError:
                return True
            _lock(stream, False)
        return False
    except OSError:
        return False


def stop_path(root: str | Path) -> Path:
    return Path(root) / "state" / "watch.stop"


def request_stop(root: str | Path, timeout: float = 180) -> None:
    path = stop_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    deadline = time.monotonic() + timeout
    while is_running(root):
        if time.monotonic() >= deadline:
            raise RuntimeError("Watcher is finishing a sync; stop requested. Retry after it completes.")
        time.sleep(0.25)


def enable(root: str | Path, *, db_path: str, storage_path: str, env_path=None, python_path=None) -> dict:
    db, storage = confirm_source(db_path, storage_path)
    from paper_compass.runtime_env import assert_managed_runtime_active
    from paper_compass.resources import resolve_stage_script
    if python_path:
        managed_python = Path(python_path).resolve()
    else:
        managed_python = assert_managed_runtime_active(context="watch autostart").managed_python
    if not managed_python.is_file():
        raise RuntimeError(f"Watcher interpreter missing: {managed_python}")
    for name in ("sync_zotero.py", "build_index.py", "ingest_to_wiki.py"):
        if not resolve_stage_script(name).is_file():
            raise RuntimeError(f"Sync stage resource missing: {name}")
    if load_config(root):
        disable(root)
    elif is_running(root):
        request_stop(root)
    data = save_choice(root, enabled=False, db_path=db, storage_path=storage, env_path=env_path)
    # Persist a complete configuration before the native manager starts the process.
    data.update(enabled=True, decision="accepted", python=str(managed_python))
    write_json(config_path(root), data)
    stop_path(root).unlink(missing_ok=True)
    try:
        watch_autostart.enable(data)
    except (OSError, RuntimeError) as exc:
        data.update(enabled=False, decision="accepted", error=str(exc))
        write_json(config_path(root), data)
        raise
    return data


def disable(root: str | Path) -> dict:
    data = load_config(root)
    if not data:
        return {"enabled": False, "decision": "declined"}
    data.update(enabled=False, decision="declined")
    write_json(config_path(root), data)
    request_stop(root)
    try:
        watch_autostart.disable(data)
    except (OSError, RuntimeError) as exc:
        data["error"] = str(exc)
        write_json(config_path(root), data)
        raise
    return data


def status(root: str | Path) -> dict:
    data = load_config(root)
    native = watch_autostart.inspect(data) if data else {"registered": False, "running": False}
    runtime = read_json(Path(root) / "state" / "watch_runtime.json")
    return {
        "enabled": bool(data.get("enabled")), "decision": data.get("decision", "unconfigured"),
        **native, "running": is_running(root), "manager_running": native.get("running", False),
        "db_path": data.get("db_path", ""), "storage_path": data.get("storage_path", ""),
        "config_path": str(config_path(root)), "log_path": str(Path(root) / "logs" / "watch.log"),
        "pid": runtime.get("pid"), "last_error": runtime.get("last_error") or data.get("error") or native.get("error", ""),
    }


def offer(root: str | Path, db_path: str, storage_path: str, *, env_path=None,
          interactive: bool = False, choice: bool | None = None, python_path=None) -> None:
    prior = load_config(root)
    if choice is False:
        if prior.get("enabled"):
            disable(root)
        else:
            save_choice(root, enabled=False, db_path=db_path, storage_path=storage_path, env_path=env_path)
        return
    if choice is None and not interactive:
        return
    db, storage = confirm_source(db_path, storage_path)
    if choice is None:
        if prior.get("decision") and prior.get("db_path") == db and prior.get("storage_path") == storage:
            return
        print(f"Zotero database: {db}\nZotero storage: {storage}")
        print("Automatic updates read Zotero without modifying it. New embeddings/wiki generation may incur API charges.")
        try:
            choice = input("Enable automatic updates and start at user login? [y/N] ").strip().lower() in {"y", "yes"}
        except (EOFError, KeyboardInterrupt):
            choice = False
    if choice:
        enable(root, db_path=db, storage_path=storage, env_path=env_path, python_path=python_path)
        print("Automatic updates enabled for user login.")
    else:
        if prior.get("enabled"):
            disable(root)
        save_choice(root, enabled=False, db_path=db, storage_path=storage, env_path=env_path)
        print("Automatic updates not enabled.")
