from __future__ import annotations

from pathlib import Path

from paper_compass.wiki_store import save_query_to_wiki


def test_save_query_to_wiki_creates_unique_filename_for_same_slug_different_keys(tmp_path):
    wiki_root = tmp_path / "wiki"

    first = save_query_to_wiki(
        title="Same Title",
        content="first",
        target_type="papers",
        source_refs=["zotero:A1"],
        wiki_root=str(wiki_root),
        upsert_mode="create_unique",
    )
    second = save_query_to_wiki(
        title="Same Title",
        content="second",
        target_type="papers",
        source_refs=["zotero:B2"],
        wiki_root=str(wiki_root),
        upsert_mode="create_unique",
    )

    assert Path(first["page_path"]).exists()
    assert Path(second["page_path"]).exists()
    assert first["page_path"] != second["page_path"]
    assert Path(second["page_path"]).name.endswith("-same-title-b2.md")


def test_save_query_to_wiki_replaces_same_key_page_when_requested(tmp_path):
    wiki_root = tmp_path / "wiki"

    first = save_query_to_wiki(
        title="Same Title",
        content="first version",
        target_type="papers",
        source_refs=["zotero:A1"],
        wiki_root=str(wiki_root),
        upsert_mode="create_unique",
    )
    second = save_query_to_wiki(
        title="Same Title",
        content="second version",
        target_type="papers",
        source_refs=["zotero:A1"],
        wiki_root=str(wiki_root),
        upsert_mode="replace_if_same_key",
    )

    page_path = Path(first["page_path"])
    assert second["page_path"] == first["page_path"]
    assert "second version" in page_path.read_text(encoding="utf-8")
