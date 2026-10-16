from pathlib import Path
from types import SimpleNamespace

from paper_compass import watcher
from paper_compass.watcher import ZoteroChangeHandler, changed_keys


def test_watcher_groups_storage_events_by_key(tmp_path: Path):
    root = tmp_path / "storage"
    root.mkdir()
    handler = ZoteroChangeHandler(root, None, lambda _: None)
    handler.on_any_event(SimpleNamespace(is_directory=False, src_path=str(root / "ABC" / "paper.pdf")))
    handler.on_any_event(SimpleNamespace(is_directory=False, src_path=str(root / "ABC" / ".zotero-ft-cache")))
    assert handler.pop() == {"ABC"}


def test_watcher_records_directory_events(tmp_path: Path):
    root = tmp_path / "storage"
    root.mkdir()
    handler = ZoteroChangeHandler(root, None, lambda _: None)
    handler.on_any_event(
        SimpleNamespace(is_directory=True, src_path=str(root / "ABC"), dest_path=str(root / "DEF"))
    )
    assert handler.pop() == {"ABC", "DEF"}


def test_run_watch_initializes_reconcile_and_watches_missing_sqlite_parent(monkeypatch, tmp_path: Path):
    root = tmp_path / "storage"
    root.mkdir()
    sqlite_path = tmp_path / "profile" / "zotero.sqlite"
    sqlite_path.parent.mkdir()
    observer = SimpleNamespace(
        schedule=lambda *args, **kwargs: schedules.append((args, kwargs)),
        start=lambda: None,
        stop=lambda: None,
        join=lambda **kwargs: None,
    )
    schedules = []
    stopped = False

    def stop_sleep(_seconds):
        nonlocal stopped
        stopped = True
        stop_event.set()

    import threading

    stop_event = threading.Event()
    monkeypatch.setattr(watcher, "Observer", lambda: observer)
    monkeypatch.setattr(watcher.time, "sleep", stop_sleep)
    watcher.run_watch(root, sqlite_path, lambda _: None, stop_event=stop_event)
    assert len(schedules) == 2
    assert schedules[0][0][1] == str(root)
    assert schedules[1][0][1] == str(sqlite_path.parent)
    assert stopped


def test_sqlite_wal_is_metadata_change(tmp_path):
    db = tmp_path / "zotero.sqlite"
    handler = ZoteroChangeHandler(tmp_path / "storage", db, lambda _: None)
    handler._record(str(db) + "-wal")
    handler._record(str(tmp_path / "unrelated.txt"))
    assert handler.pop() == {"__metadata__"}


def test_reconciliation_and_cleanup(monkeypatch, tmp_path):
    import threading
    from unittest.mock import MagicMock

    stop = threading.Event()
    observer = MagicMock()
    clock = iter([0.0, 10.0])
    calls = []
    def callback(events):
        calls.append(events)
        stop.set()
    monkeypatch.setattr(watcher, "Observer", lambda: observer)
    monkeypatch.setattr(watcher.time, "sleep", lambda _: None)
    monkeypatch.setattr(watcher.time, "monotonic", lambda: next(clock))
    watcher.run_watch(tmp_path, None, callback, reconcile_seconds=5, stop_event=stop)
    assert calls == [{"__reconcile__"}]
    observer.stop.assert_called_once()
    observer.join.assert_called_once_with(timeout=10)


def test_real_observer_receives_storage_changes(tmp_path):
    import threading

    received = threading.Event()
    stop = threading.Event()
    root = tmp_path / "storage"
    root.mkdir()
    observer_thread = threading.Thread(
        target=watcher.run_watch,
        args=(root, None, lambda keys: received.set() if "ABC" in keys else None),
        kwargs={"debounce_seconds": 0.1, "reconcile_seconds": 600, "stop_event": stop},
    )
    observer_thread.start()
    try:
        # A temporary item exercises the real OS observer without touching Zotero.
        import time
        time.sleep(0.5)
        item = root / "ABC"
        item.mkdir()
        paper = item / "paper.txt"
        paper.write_text("first", encoding="utf-8")
        assert received.wait(5), "creation event missing"
        received.clear()
        paper.write_text("second", encoding="utf-8")
        assert received.wait(5), "modification event missing"
        received.clear()
        moved = item / "renamed.txt"
        paper.rename(moved)
        assert received.wait(5), "rename event missing"
        received.clear()
        moved.unlink()
        item.rmdir()
        assert received.wait(5), "deletion event missing"
    finally:
        stop.set()
        observer_thread.join(timeout=10)
    assert not observer_thread.is_alive()


def test_read_events_do_not_trigger_changes(tmp_path):
    handler = ZoteroChangeHandler(tmp_path, None, lambda _: None)
    for event_type in ("opened", "closed_no_write", "accessed"):
        handler.on_any_event(SimpleNamespace(src_path=str(tmp_path / "ABC" / "paper.pdf"), event_type=event_type))
    assert handler.pop() == set()


def test_strict_watch_does_not_create_missing_storage(tmp_path):
    import pytest
    root = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        watcher.run_watch(root, None, lambda _: None, require_existing=True)
    assert not root.exists()


def test_changed_keys_excludes_control_events():
    assert changed_keys({"ABC", "__metadata__", "__reconcile__"}) == {"ABC"}
