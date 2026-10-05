"""Tests for stable passage-handle readback."""

import json

import pytest

from paper_compass.mcp_views import shape_passage_matches
from paper_compass.passage_reader import get_passage_context
from paper_compass.search import search_passages


def _write_library(path):
    path.write_text(
        json.dumps(
            [
                {
                    "key": "ABC123",
                    "title": "Stable Readback Paper",
                    "year": 2026,
                }
            ]
        ),
        encoding="utf-8",
    )


def _write_abc_text(text_dir, *, second_extra=""):
    text_dir.mkdir(parents=True, exist_ok=True)
    first = (
        "First valid paragraph has enough characters to survive filtering "
        "and should be ordinal zero."
    )
    second = (
        "Second valid paragraph is the stable target for ordinal one; it must "
        "be returned without performing a fresh search."
        f"{second_extra}"
    )
    third = "Third valid paragraph also has enough length to be included."
    (text_dir / "ABC123.txt").write_text(
        "Title\n\n"
        f"{first}\n\n"
        "tiny\n\n"
        f"{second}\n\n"
        f"{third}\n",
        encoding="utf-8",
    )
    return first, second, third


def test_keyword_handle_resolves_from_text_without_second_search(tmp_path, monkeypatch):
    text_dir = tmp_path / "texts"
    library_path = tmp_path / "library.json"
    _write_library(library_path)
    _, second, _ = _write_abc_text(text_dir)

    def fail_search(*args, **kwargs):  # pragma: no cover - should not be reached
        raise AssertionError("keyword readback must not call search_passages")

    monkeypatch.setattr("paper_compass.passage_reader.search_passages", fail_search)

    context = get_passage_context(
        "passage:ABC123:p?:keyword:1",
        text_dir=str(text_dir),
        library_path=str(library_path),
    )

    assert context["paper_handle"] == "paper:ABC123"
    assert context["passage_handle"] == "passage:ABC123:p?:keyword:1"
    assert context["title"] == "Stable Readback Paper"
    assert context["page_num"] is None
    assert context["context_window"] == "paragraph"
    assert context["text"] == second


def test_keyword_match_only_caps_to_min_of_max_chars_and_400(tmp_path, monkeypatch):
    text_dir = tmp_path / "texts"
    library_path = tmp_path / "library.json"
    _write_library(library_path)
    _, second, _ = _write_abc_text(text_dir, second_extra=" extra words" * 100)
    monkeypatch.setattr(
        "paper_compass.passage_reader.search_passages",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no search")),
    )

    context_400 = get_passage_context(
        "passage:ABC123:p?:keyword:1",
        window="match_only",
        max_chars=1000,
        text_dir=str(text_dir),
        library_path=str(library_path),
    )
    context_120 = get_passage_context(
        "passage:ABC123:p?:keyword:1",
        window="match_only",
        max_chars=120,
        text_dir=str(text_dir),
        library_path=str(library_path),
    )

    assert context_400["text"] == second[:400]
    assert len(context_400["text"]) <= 400
    assert context_120["text"] == second[:120]
    assert len(context_120["text"]) <= 120


def test_keyword_search_handle_uses_stable_paragraph_ordinal(tmp_path):
    text_dir = tmp_path / "texts"
    library_path = tmp_path / "library.json"
    _write_library(library_path)
    _write_abc_text(text_dir)

    results = search_passages(
        "Third",
        search_mode="keyword",
        limit=1,
        text_dir=str(text_dir),
        library_path=str(library_path),
        db_path=str(tmp_path / "missing_vectordb"),
    )
    shaped = shape_passage_matches(results)

    assert shaped[0]["passage_handle"] == "passage:ABC123:p?:keyword:2"
    context = get_passage_context(
        shaped[0]["passage_handle"],
        text_dir=str(text_dir),
        library_path=str(library_path),
    )
    assert context["text"].startswith("Third valid paragraph")


def test_keyword_handle_with_missing_ordinal_raises_clear_value_error(tmp_path, monkeypatch):
    text_dir = tmp_path / "texts"
    library_path = tmp_path / "library.json"
    _write_library(library_path)
    _write_abc_text(text_dir)
    monkeypatch.setattr(
        "paper_compass.passage_reader.search_passages",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no search")),
    )

    with pytest.raises(ValueError, match="Could not resolve passage handle.*ordinal 99"):
        get_passage_context(
            "passage:ABC123:p?:keyword:99",
            text_dir=str(text_dir),
            library_path=str(library_path),
        )
