from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from helpers import load_build_index


def _load_sync_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "sync_zotero.py"
    spec = importlib.util.spec_from_file_location("paper_compass_sync_zotero_safety", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _candidate(key: str, source_kind: str, source_path: Path):
    return SimpleNamespace(key=key, source_kind=source_kind, source_path=source_path)


def test_incremental_prune_keeps_raw_keys_skipped_during_preparation():
    module = load_build_index()

    result = module._prunable_keys_excluding_raw_items(
        ["missing", "offline", "orphan"],
        [{"key": "offline"}, {"key": "missing"}],
    )

    assert result == ["orphan"]


def test_managed_sync_blocks_active_prior_key_with_missing_source(tmp_path):
    module = _load_sync_module()
    previous = [{"key": "P1", "pdf_path": str(tmp_path / "old.pdf")}]
    metadata = [{"key": "P1", "attachment_key": "A1", "pdf_path": str(tmp_path / "new.pdf")}]

    assert module.managed_source_safety_violations(previous, metadata, []) == ["P1"]


def test_managed_sync_accepts_existing_pdf_even_when_old_runtime_text_was_missing(tmp_path):
    module = _load_sync_module()
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    previous = [{"key": "P1", "pdf_path": str(tmp_path / "old.pdf")}]
    metadata = [{"key": "P1", "attachment_key": "A1"}]

    assert module.managed_source_safety_violations(
        previous, metadata, [_candidate("A1", "pdf", pdf)]
    ) == []


def test_managed_sync_blocks_empty_cache_source(tmp_path):
    module = _load_sync_module()
    cache = tmp_path / ".zotero-ft-cache"
    cache.write_text("", encoding="utf-8")
    previous = [{"key": "P1", "pdf_path": str(tmp_path / "old.pdf")}]
    metadata = [{"key": "P1", "attachment_key": "A1"}]

    assert module.managed_source_safety_violations(
        previous, metadata, [_candidate("A1", "ft_cache", cache)]
    ) == ["P1"]


def test_managed_sync_allows_prior_key_absent_from_active_metadata(tmp_path):
    module = _load_sync_module()
    previous = [{"key": "P1", "pdf_path": str(tmp_path / "old.pdf")}]

    assert module.managed_source_safety_violations(previous, [], []) == []
