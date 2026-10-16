"""paper-compass watch subcommand."""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from paper_compass.config import resolve_path_settings
from paper_compass.console_window import child_creation_flags
from paper_compass.env_utils import PROJECT_ROOT, load_project_env
from paper_compass import watch_service
from paper_compass.watcher import run_watch


def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("watch", help="Watch Zotero or manage login autostart")
    parser.add_argument("--storage-path", default="", help="Zotero storage directory")
    parser.add_argument("--sqlite-path", default="", help="Zotero SQLite database path")
    parser.add_argument("--debounce-seconds", type=float, default=3.0)
    parser.add_argument("--reconcile-seconds", type=float, default=600.0)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--once", action="store_true", help="Reconcile once and exit")
    modes.add_argument("--enable-autostart", action="store_true", help="Enable user-login automatic updates")
    modes.add_argument("--disable-autostart", action="store_true", help="Disable login updates and stop after current sync")
    modes.add_argument("--autostart-status", action="store_true", help="Report actual login service and watcher state")
    modes.add_argument("--managed", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--watch-config", help=argparse.SUPPRESS)
    parser.set_defaults(func=execute_watch)


class _LogStream:
    def __init__(self, logger, level):
        self.logger, self.level = logger, level
    def write(self, text):
        for line in text.splitlines():
            if line.strip():
                self.logger.log(self.level, line)
        return len(text)
    def flush(self):
        for handler in self.logger.handlers:
            handler.flush()


def _managed(config_path: str) -> int:
    data = watch_service.read_json(Path(config_path))
    if data.get("version") != 1 or not data.get("enabled"):
        print("Managed watcher configuration is disabled or invalid", file=sys.stderr)
        return 2
    root = Path(data["runtime_root"])
    log_path = root / "logs" / "watch.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("paper_compass.managed_watch")
    logger.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _LogStream(logger, logging.INFO), _LogStream(logger, logging.ERROR)
    stopper = threading.Event()
    previous_handlers = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[sig] = signal.signal(sig, lambda *_: stopper.set())
    state_path = root / "state" / "watch_runtime.json"
    previous_env = {key: os.environ.get(key) for key in ("PAPER_COMPASS_ROOT", "PAPER_COMPASS_ENV_PATH", "PYTHONUTF8", "PYTHONIOENCODING", "PAPER_COMPASS_MANAGED_WATCH")}
    def stopped():
        return stopper.is_set() or watch_service.stop_path(root).exists() or not watch_service.read_json(Path(config_path)).get("enabled")
    def record(error=""):
        watch_service.write_json(state_path, {"pid": os.getpid(), "updated_at": time.time(), "last_error": error})
    try:
        with watch_service.instance_lock(root):
            load_project_env(data["env_path"])
            os.environ.update(PAPER_COMPASS_ROOT=str(root), PAPER_COMPASS_ENV_PATH=data["env_path"], PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PAPER_COMPASS_MANAGED_WATCH="1")
            print(f"Managed watcher started: database={data['db_path']} storage={data['storage_path']}")
            record()
            def sync(events):
                if stopped():
                    return
                try:
                    watch_service.confirm_source(data["db_path"], data["storage_path"])
                    command = [data["python"], "-m", "paper_compass", "sync", "--snapshot-db", "always", "--db-source-path", data["db_path"], "--storage-path", data["storage_path"]]
                    print(f"Incremental sync: {', '.join(sorted(events))}")
                    # A pipe reader forwards child output into the bounded rotating log.
                    # The watcher runs detached with no console, so the console-less
                    # parent would otherwise give the child a fresh, focus-stealing window.
                    with subprocess.Popen(command, cwd=data["project_root"], env=os.environ.copy(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=child_creation_flags()) as child:
                        for line in child.stdout:
                            print(line.rstrip())
                        code = child.wait()
                    error = f"Sync failed with exit code {code}" if code else ""
                    record(error)
                    if error:
                        print(error, file=sys.stderr)
                except (OSError, ValueError) as exc:
                    record(str(exc))
                    print(str(exc), file=sys.stderr)
            def monitor_stop():
                while not stopper.wait(0.25):
                    if stopped():
                        stopper.set()
            thread = threading.Thread(target=monitor_stop, daemon=True)
            thread.start()
            needs_reconcile = True
            while not stopped():
                try:
                    watch_service.confirm_source(data["db_path"], data["storage_path"])
                    if needs_reconcile:
                        sync({"__startup__"})
                        needs_reconcile = False
                    run_watch(data["storage_path"], data["db_path"], sync, debounce_seconds=data["debounce_seconds"], reconcile_seconds=data["reconcile_seconds"], stop_event=stopper, require_existing=True)
                except (OSError, ValueError) as exc:
                    record(str(exc))
                    print(f"Waiting for Zotero source: {exc}", file=sys.stderr)
                    needs_reconcile = True
                    stopper.wait(30)
            print("Managed watcher stopped after completing active sync")
            stopper.set()
            thread.join(timeout=1)
    except watch_service.WatchAlreadyRunning as exc:
        print(str(exc))
        return 0
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
        for sig, value in previous_handlers.items():
            signal.signal(sig, value)
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        logger.removeHandler(handler)
        handler.close()
    return 0


def execute_watch(args: argparse.Namespace) -> int:
    if getattr(args, "managed", False):
        return _managed(args.watch_config or str(watch_service.config_path(os.environ.get("PAPER_COMPASS_ROOT") or Path.home() / ".paper-compass")))
    load_project_env()
    initial = resolve_path_settings()
    root = Path(getattr(initial, "compass_root", "") or os.environ.get("PAPER_COMPASS_ROOT") or Path.home() / ".paper-compass")
    if getattr(args, "autostart_status", False):
        print(json.dumps(watch_service.status(root), indent=2, ensure_ascii=False))
        return 0
    if getattr(args, "disable_autostart", False):
        try:
            watch_service.disable(root)
        except (OSError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print("Automatic login updates disabled")
        return 0
    saved = watch_service.load_config(root)
    settings = resolve_path_settings(overrides={"zotero_storage_path": args.storage_path, "zotero_sqlite_path": args.sqlite_path}, local_paths={"zotero_storage_path": saved.get("storage_path"), "zotero_sqlite_path": saved.get("db_path")})
    storage_path = str(Path(settings.zotero_storage_path).resolve()) if settings.zotero_storage_path else ""
    sqlite_path = str(Path(settings.zotero_sqlite_path).resolve()) if settings.zotero_sqlite_path else ""
    if not storage_path:
        print("watch requires PAPER_COMPASS_ZOTERO_ROOT or --storage-path")
        return 2
    if getattr(args, "enable_autostart", False):
        try:
            watch_service.enable(root, db_path=sqlite_path, storage_path=storage_path)
        except (OSError, RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print("Automatic updates enabled for user login")
        return 0

    def sync(events):
        print(f"watch sync triggered: {', '.join(sorted(events))}", flush=True)
        command = [sys.executable, "-m", "paper_compass", "sync"]
        if sqlite_path:
            command += ["--db-source-path", sqlite_path]
        command += ["--storage-path", storage_path]
        result = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False, creationflags=child_creation_flags())
        if result.returncode:
            print(f"watch sync failed with exit code {result.returncode}", file=sys.stderr)
        return result.returncode
    if args.once:
        return sync({"__reconcile__"})
    print(f"watch storage: {storage_path}", flush=True)
    print(f"watch SQLite: {sqlite_path or '(not configured)'}", flush=True)
    stopper = threading.Event()
    def stop_monitor():
        while not stopper.wait(0.25):
            if watch_service.stop_path(root).exists():
                stopper.set()
    try:
        with watch_service.instance_lock(root):
            watch_service.stop_path(root).unlink(missing_ok=True)
            thread = threading.Thread(target=stop_monitor, daemon=True)
            thread.start()
            try:
                run_watch(storage_path, sqlite_path or None, sync, debounce_seconds=max(0.25, args.debounce_seconds), reconcile_seconds=max(30.0, args.reconcile_seconds), stop_event=stopper)
            finally:
                stopper.set()
                thread.join(timeout=1)
    except KeyboardInterrupt:
        return 0
    except watch_service.WatchAlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0
