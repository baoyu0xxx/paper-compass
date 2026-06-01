from __future__ import annotations

import json
from pathlib import Path


def test_existing_text_file_can_be_reused_without_extract_text(tmp_path):
    out_dir = tmp_path / "data" / "zotero-export"
    text_dir = tmp_path / "data" / "texts"
    out_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    item = {
        "item_id": "1",
        "key": "ZGV8IA5N",
        "title": "Feature augmentations for high-dimensional learning",
        "date": "2025-08-29",
        "authors": ["Zhu"],
        "tags": [],
        "collections": ["组会文章"],
        "attachment_key": "9GF4GARI",
        "attachment_path": "storage:file.pdf",
        "item_type": "journalArticle",
        "pdf_path": str(tmp_path / "file.pdf"),
    }
    (tmp_path / "file.pdf").write_text("pdf placeholder", encoding="utf-8")
    existing_text = text_dir / "ZGV8IA5N.txt"
    existing_text.write_text("already extracted", encoding="utf-8")

    if existing_text.exists():
        item["text_file"] = str(existing_text)

    library_path = out_dir / "library.json"
    library_path.write_text(json.dumps([item], ensure_ascii=False, indent=2), encoding="utf-8")

    payload = json.loads(library_path.read_text(encoding="utf-8"))
    assert payload[0]["text_file"].endswith("ZGV8IA5N.txt")
