from pathlib import Path

from paper_compass.index_manifest import build_paper_fingerprint, diff_manifest_v2


def _item(tmp_path: Path, *, key="A1", title="Title", tags=None, pdf_name="A1.pdf", text_file=""):
    pdf = tmp_path / pdf_name
    pdf.write_bytes(b"same pdf bytes")
    return {
        "key": key,
        "title": title,
        "year": 2020,
        "authors": ["A"],
        "collections": ["C"],
        "tags": tags or ["T"],
        "pdf_path": str(pdf),
        "text_file": text_file,
    }


def test_manifest_v2_classifies_metadata_change_without_reembedding(tmp_path):
    text = "same extracted text" * 200
    old_item = _item(tmp_path, title="Old title", tags=["old"])
    new_item = {**old_item, "title": "New title", "tags": ["new"]}

    previous = {
        "A1": build_paper_fingerprint(old_item, text, "chunks-v1", "embed-v1", chunk_count=2)
    }
    current = {
        "A1": build_paper_fingerprint(new_item, text, "chunks-v1", "embed-v1", chunk_count=2)
    }

    diff = diff_manifest_v2(current, previous)

    assert diff["metadata_only"] == ["A1"]
    assert diff["requires_embedding"] == []
    assert diff["unchanged"] == []


def test_manifest_v2_classifies_path_change_without_reembedding(tmp_path):
    text = "same extracted text" * 200
    text_a = tmp_path / "old" / "A1.txt"
    text_a.parent.mkdir()
    text_a.write_text(text, encoding="utf-8")
    text_b = tmp_path / "new" / "A1.txt"
    text_b.parent.mkdir()
    text_b.write_text(text, encoding="utf-8")

    item_a = _item(tmp_path, text_file=str(text_a))
    item_b = {**item_a, "text_file": str(text_b)}

    previous = {"A1": build_paper_fingerprint(item_a, text, "chunks-v1", "embed-v1", chunk_count=2)}
    current = {"A1": build_paper_fingerprint(item_b, text, "chunks-v1", "embed-v1", chunk_count=2)}

    diff = diff_manifest_v2(current, previous)

    assert diff["path_only"] == ["A1"]
    assert diff["requires_embedding"] == []


def test_manifest_v2_uses_text_content_when_pdf_is_missing(tmp_path):
    item = _item(tmp_path)
    Path(item["pdf_path"]).unlink()
    previous = {"A1": build_paper_fingerprint(item, "old text" * 200, "chunks-v1", "embed-v1", chunk_count=2)}
    current = {"A1": build_paper_fingerprint(item, "new text" * 200, "chunks-v1", "embed-v1", chunk_count=2)}

    diff = diff_manifest_v2(current, previous)

    assert diff["content_changed"] == ["A1"]
    assert diff["requires_embedding"] == ["A1"]


def test_manifest_v2_does_not_reembed_when_extracted_text_changes_but_pdf_is_same(tmp_path):
    item = _item(tmp_path)
    previous = {"A1": build_paper_fingerprint(item, "old text" * 200, "chunks-v1", "embed-v1", chunk_count=2)}
    current = {"A1": build_paper_fingerprint(item, "new text" * 200, "chunks-v1", "embed-v1", chunk_count=2)}

    diff = diff_manifest_v2(current, previous)

    assert diff["requires_embedding"] == []
    assert diff["content_changed"] == []


def test_manifest_v2_keeps_old_manifest_content_compatible(tmp_path):
    item = _item(tmp_path)
    current = {"A1": build_paper_fingerprint(item, "same text" * 200, "chunks-v1", "embed-v1", chunk_count=2)}
    previous = {
        "A1": {
            "item_key": "A1",
            "text_sha1": current["A1"]["source"]["text_sha1"],
            "text_size": current["A1"]["source"]["text_size"],
            "chunking_version": "chunks-v1",
            "chunk_count": 2,
            "embedding_model_id": "old-embed-model",
            "pdf_path": str(tmp_path / "old-location.pdf"),
        }
    }

    diff = diff_manifest_v2(current, previous)

    assert diff["requires_embedding"] == []
    assert diff["content_changed"] == []
