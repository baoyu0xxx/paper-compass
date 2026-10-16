"""Passive Zotero storage watcher with debounced sync callbacks."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Iterable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class ZoteroChangeHandler(FileSystemEventHandler):
    def __init__(self, storage_root: Path, sqlite_path: Path | None, on_change: Callable[[set[str]], None]):
        super().__init__()
        self.storage_root = storage_root
        self.sqlite_path = sqlite_path
        self.on_change = on_change
        self._changed: set[str] = set()
        self._lock = threading.Lock()

    def _record(self, path: str) -> None:
        changed = Path(path)
        if self.sqlite_path and changed in {
            self.sqlite_path,
            Path(str(self.sqlite_path) + "-wal"),
            Path(str(self.sqlite_path) + "-journal"),
        }:
            key = "__metadata__"
        else:
            try:
                relative = changed.relative_to(self.storage_root)
                key = relative.parts[0] if relative.parts else "__root__"
            except ValueError:
                return
        with self._lock:
            self._changed.add(key)

    def pop(self) -> set[str]:
        with self._lock:
            changed, self._changed = self._changed, set()
            return changed

    def on_any_event(self, event) -> None:  # watchdog event protocol
        if getattr(event, "event_type", "") in {"opened", "closed", "closed_no_write", "accessed"}:
            return
        self._record(event.src_path)
        if getattr(event, "dest_path", None):
            self._record(event.dest_path)


def run_watch(
    storage_root: str | Path,
    sqlite_path: str | Path | None,
    on_change: Callable[[set[str]], None],
    *,
    debounce_seconds: float = 3.0,
    reconcile_seconds: float = 600.0,
    stop_event: threading.Event | None = None,
    require_existing: bool = False,
) -> None:
    """Run an event-driven watcher until stop_event is set or interrupted."""
    root = Path(storage_root)
    db_path = Path(sqlite_path) if sqlite_path else None
    if require_existing:
        if not root.is_dir():
            raise FileNotFoundError(f"Zotero storage unavailable: {root}")
    else:
        root.mkdir(parents=True, exist_ok=True)
    stopper = stop_event or threading.Event()
    handler = ZoteroChangeHandler(root, db_path, on_change)
    observer = Observer()
    observer.schedule(handler, str(root), recursive=True)
    if db_path:
        db_parent = db_path.parent
        if db_parent.exists():
            observer.schedule(handler, str(db_parent), recursive=False)
    observer.start()
    pending: set[str] = set()
    pending_since: float | None = None
    last_reconcile = time.monotonic()
    source_identity = (root.stat().st_dev, root.stat().st_ino)
    try:
        while not stopper.is_set():
            time.sleep(0.25)
            if require_existing:
                if not root.is_dir():
                    raise FileNotFoundError(f"Zotero storage unavailable: {root}")
                identity = (root.stat().st_dev, root.stat().st_ino)
                if identity != source_identity:
                    raise FileNotFoundError("Zotero storage replaced; rebind observer")
            changed = handler.pop()
            if changed:
                pending.update(changed)
                if pending_since is None:
                    pending_since = time.monotonic()
            now = time.monotonic()
            due = now - last_reconcile >= reconcile_seconds
            if pending and pending_since is not None and now - pending_since >= debounce_seconds:
                on_change(set(pending) | ({"__reconcile__"} if due else set()))
                pending.clear()
                pending_since = None
                last_reconcile = now
            elif due:
                on_change({"__reconcile__"})
                last_reconcile = now
    finally:
        observer.stop()
        observer.join(timeout=10)


def changed_keys(events: Iterable[str]) -> set[str]:
    return {key for key in events if key and not key.startswith("__")}
