"""Tests for library/passage search — keyword, semantic, filters, ranking."""

import json
from pathlib import Path

import pytest

from helpers import write_fake_library
from paper_compass.search import (
    _keyword_search_passages,
    get_paper_metadata,
    search_library,
    search_passages,
)


# ── Text file helper (passage search needs real text files) ──────────────


def _write_text_files(text_dir: Path):
    text_dir.mkdir(parents=True, exist_ok=True)
    (text_dir / "ABC123.txt").write_text(
        "Abstract\n\n"
        "This paper examines the relationship between family firm succession "
        "and labor structure changes.\n\n"
        "Introduction\n\n"
        "Family firms play a critical role in many economies. Succession is a "
        "key event that can reshape the internal structure of the workforce. "
        "We use a difference-in-differences approach to identify causal effects "
        "of CEO succession on employment composition.\n\n"
        "Data and Methods\n\n"
        "We collect data from listed Chinese family firms between 2008 and 2022. "
        "Our sample includes over 400 firms and 5200 firm-year observations. "
        "The treatment group consists of firms that experienced intra-family "
        "CEO succession.\n\n"
        "Results\n\n"
        "We find that family firm succession leads to a significant shift in "
        "labor structure, with a notable increase in high-skill worker share "
        "and a decrease in low-skill worker share.\n"
    )
    (text_dir / "DEF456.txt").write_text(
        "Abstract\n\n"
        "This paper studies the dynamics of family business employment patterns "
        "over time.\n\n"
        "Introduction\n\n"
        "Family businesses exhibit distinct employment patterns compared to "
        "non-family firms. We investigate how succession events affect labor "
        "force composition.\n\n"
        "Results\n\n"
        "Succession leads to greater employment stability in family firms "
        "compared to non-family peers.\n"
    )


# ═══════════════════════════════════════════════════════════════════════
# Library-level search tests (from test_retrieval_quality.py)
# ═══════════════════════════════════════════════════════════════════════


class TestLibraryExactMatch:
    """Precision/ranking tests for search_library exact-match logic."""

    def test_exact_key_match_ranked_first(self, tmp_path):
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_library("ABC123", library_path=str(lib), limit=3)
        assert results
        assert results[0]["doc_id"] == "ABC123"

    def test_exact_doi_match_ranked_first(self, tmp_path):
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_library(
            "10.1000/family.001", library_path=str(lib), limit=3
        )
        assert results
        assert results[0]["doi"] == "10.1000/family.001"

    def test_exact_normalized_title_match_ranked_first(self, tmp_path):
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_library(
            "family firm succession and labor structure",
            library_path=str(lib),
            limit=3,
        )
        assert results
        assert results[0]["title"] == "Family Firm Succession and Labor Structure"


# ═══════════════════════════════════════════════════════════════════════
# Passage search — keyword mode
# ═══════════════════════════════════════════════════════════════════════


class TestSearchPassagesKeyword:
    def test_keyword_search_finds_paragraphs(self, tmp_path):
        _write_text_files(tmp_path)
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_passages(
            "labor structure",
            search_mode="keyword",
            limit=5,
            text_dir=str(tmp_path),
            library_path=str(lib),
            db_path=str(tmp_path / "nonexistent_vectordb"),
        )
        assert len(results) > 0, "Keyword search should find matching paragraphs"
        # Check enrichment
        enriched = [r for r in results if r["title"]]
        assert len(enriched) > 0, (
            "At least some results should be enriched with metadata"
        )

    def test_keyword_search_respects_limit(self, tmp_path):
        _write_text_files(tmp_path)
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_passages(
            "family firm",
            search_mode="keyword",
            limit=2,
            text_dir=str(tmp_path),
            library_path=str(lib),
            db_path=str(tmp_path / "nonexistent_vectordb"),
        )
        assert len(results) <= 2

    def test_keyword_search_skips_short_paragraphs(self, tmp_path):
        text_dir = tmp_path / "texts"
        text_dir.mkdir()
        (text_dir / "SHORT.txt").write_text("hi\n\ntiny")
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_passages(
            "hi",
            search_mode="keyword",
            text_dir=str(text_dir),
            library_path=str(lib),
            db_path=str(tmp_path / "nonexistent_vectordb"),
        )
        # No paragraph >= 30 chars containing "hi"
        for r in results:
            assert len(r["passage"]) >= 30

    def test_keyword_search_empty_text_dir(self, tmp_path):
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_passages(
            "anything",
            search_mode="keyword",
            text_dir=str(tmp_path / "nonexistent"),
            library_path=str(lib),
            db_path=str(tmp_path / "nonexistent_vectordb"),
        )
        assert results == []

    def test_keyword_search_returns_structure(self, tmp_path):
        _write_text_files(tmp_path)
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_passages(
            "succession",
            search_mode="keyword",
            limit=3,
            text_dir=str(tmp_path),
            library_path=str(lib),
            db_path=str(tmp_path / "nonexistent_vectordb"),
        )
        for r in results:
            assert "passage" in r
            assert "score" in r
            assert "search_mode" in r
            assert r["search_mode"] == "keyword"
            assert len(r["passage"]) > 0


# ═══════════════════════════════════════════════════════════════════════
# Passage search — filter tests
# ═══════════════════════════════════════════════════════════════════════


class TestSearchPassagesFilters:
    def test_year_filter_excludes(self, tmp_path):
        _write_text_files(tmp_path)
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results_all = search_passages(
            "family",
            search_mode="keyword",
            text_dir=str(tmp_path),
            library_path=str(lib),
            db_path=str(tmp_path / "nonexistent_vectordb"),
        )
        results_filtered = search_passages(
            "family",
            search_mode="keyword",
            filters={"year_from": 2024},
            text_dir=str(tmp_path),
            library_path=str(lib),
            db_path=str(tmp_path / "nonexistent_vectordb"),
        )
        assert len(results_filtered) <= len(results_all)

    def test_collection_filter(self, tmp_path):
        _write_text_files(tmp_path)
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_passages(
            "family",
            search_mode="keyword",
            filters={"collections": ["governance"]},
            text_dir=str(tmp_path),
            library_path=str(lib),
            db_path=str(tmp_path / "nonexistent_vectordb"),
        )
        for r in results:
            assert (
                r["title"]
                != "Family Firm Succession and Labor Structure"
                or "governance"
                in [c.lower() for c in r.get("collections", [])]
            )


# ═══════════════════════════════════════════════════════════════════════
# Passage search — semantic/hybrid mode
# ═══════════════════════════════════════════════════════════════════════


class TestSearchPassagesSemantic:
    def test_semantic_mode_graceful_on_no_vectordb(self, tmp_path):
        """Semantic search on nonexistent vectordb should return empty, not crash."""
        _write_text_files(tmp_path)
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_passages(
            "family firm succession",
            search_mode="semantic",
            db_path=str(tmp_path / "nonexistent_vectordb"),
            text_dir=str(tmp_path),
            library_path=str(lib),
        )
        assert results == []

    def test_hybrid_mode_falls_back_to_keyword(self, tmp_path):
        """Hybrid mode should return keyword results when vectordb is missing."""
        _write_text_files(tmp_path)
        lib = tmp_path / "library.json"
        write_fake_library(lib)

        results = search_passages(
            "labor structure",
            search_mode="hybrid",
            db_path=str(tmp_path / "nonexistent_vectordb"),
            text_dir=str(tmp_path),
            library_path=str(lib),
        )
        assert len(results) > 0
        # At least some results should be from keyword mode
        modes = {r["search_mode"] for r in results}
        assert "keyword" in modes


# ═══════════════════════════════════════════════════════════════════════
# Keyword search helper tests
# ═══════════════════════════════════════════════════════════════════════


class TestKeywordSearchPassagesHelper:
    def test_empty_query_returns_empty(self, tmp_path):
        text_dir = tmp_path / "texts"
        text_dir.mkdir()
        (text_dir / "test.txt").write_text("Some content here")
        results = _keyword_search_passages("", str(text_dir))
        assert results == []

    def test_no_text_files_returns_empty(self, tmp_path):
        text_dir = tmp_path / "texts"
        text_dir.mkdir()
        results = _keyword_search_passages("test", str(text_dir))
        assert results == []

    def test_deduplication(self, tmp_path):
        text_dir = tmp_path / "texts"
        text_dir.mkdir()
        (text_dir / "dup.txt").write_text(
            "Paragraph about labor.\n\n"
            "Paragraph about labor.\n\n"
            "Different paragraph about capital.\n"
        )
        results = _keyword_search_passages("labor", str(text_dir), limit=10)
        # Deduplication should prevent duplicate passages
        assert len(results) <= 2

    def test_cjk_keyword_search_matches_unsegmented_paragraph(self, tmp_path):
        text_dir = tmp_path / "texts"
        text_dir.mkdir()
        (text_dir / "CJK123.txt").write_text(
            "摘要\n\n"
            "本文研究家族企业代际传承影响劳动力结构，并进一步讨论CEO继任后的治理变化。"
        )

        results = _keyword_search_passages("代际传承", str(text_dir), limit=5)

        assert results
        assert results[0]["doc_id"] == "CJK123"
        assert "代际传承" in results[0]["passage"]
        assert results[0]["paragraph_index"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Search module — edge-case smoke tests (moved from old test_mcp_backend)
# ═══════════════════════════════════════════════════════════════════════


class TestSearchEdgeCases:
    def test_search_library_empty(self):
        from paper_compass.search import search_library

        results = search_library(
            "test", library_path="/nonexistent/library.json"
        )
        assert results == []

    def test_get_paper_metadata_empty(self):
        result = get_paper_metadata(
            "abc", library_path="/nonexistent/library.json"
        )
        assert result is None
