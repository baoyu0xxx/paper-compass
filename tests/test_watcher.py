from pathlib import Path
from types import SimpleNamespace

from paper_compass.watcher import ZoteroChangeHandler, changed_keys


def test_watcher_groups_storage_events_by_key(tmp_path: Path):
    root = tmp_path / "storage"
    root.mkdir()
    handler = ZoteroChangeHandler(root, None, lambda _: None)
    handler.on_any_event(SimpleNamespace(is_directory=False, src_path=str(root / "ABC" / "paper.pdf")))
    handler.on_any_event(SimpleNamespace(is_directory=False, src_path=str(root / "ABC" / ".zotero-ft-cache")))
    assert handler.pop() == {"ABC"}


def test_changed_keys_excludes_control_events():
    assert changed_keys({"ABC", "__metadata__", "__reconcile__"}) == {"ABC"}
