from __future__ import annotations

from pathlib import Path

from paper_compass.config import resolve_path_settings
from paper_compass.source_scanner import normalize_storage_items, scan_storage


def test_scan_storage_prefers_nonempty_cache(tmp_path: Path):
    storage = tmp_path / "storage"
    cached = storage / "CACHEKEY"
    cached.mkdir(parents=True)
    (cached / ".zotero-ft-cache").write_text("cached paper text", encoding="utf-8")
    (cached / "paper.pdf").write_bytes(b"pdf")

    pdf_only = storage / "PDFKEY"
    pdf_only.mkdir()
    (pdf_only / "paper.pdf").write_bytes(b"pdf")

    missing = storage / "EMPTYKEY"
    missing.mkdir()

    result = {item.key: item for item in scan_storage(storage)}
    assert result["CACHEKEY"].source_kind == "ft_cache"
    assert result["PDFKEY"].source_kind == "pdf"
    assert result["EMPTYKEY"].source_kind == "unavailable"


def test_normalize_storage_preserves_parent_metadata_key(tmp_path: Path):
    storage = tmp_path / "storage" / "ATTACHKEY"
    storage.mkdir(parents=True)
    (storage / ".zotero-ft-cache").write_text("Title line", encoding="utf-8")

    items = normalize_storage_items(storage.parent, [{"key": "PARENTKEY", "attachment_key": "ATTACHKEY", "title": "Known"}])
    assert items[0]["key"] == "PARENTKEY"
    assert items[0]["attachment_key"] == "ATTACHKEY"
    assert items[0]["source_kind"] == "ft_cache"


def test_compass_root_derives_runtime_paths(monkeypatch, tmp_path: Path):
    root = tmp_path / ".papercompass"
    monkeypatch.setenv("PAPER_COMPASS_ROOT", str(root))
    settings = resolve_path_settings(configs={})
    assert settings.library_json_path == str(root / "library" / "library.json")
    assert settings.text_dir == str(root / "texts")
    assert settings.vectordb_path == str(root / "index" / "vectordb")
