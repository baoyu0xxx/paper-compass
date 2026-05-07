"""Tests for Wiki query module."""

import tempfile
from pathlib import Path

import pytest

from miniresearch.wiki_query import search_wiki_pages, answer_from_wiki


@pytest.fixture
def sample_wiki(tmp_path):
    """Create a minimal wiki structure for testing."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    topics = wiki / "topics"
    topics.mkdir()
    (topics / "did.md").write_text(
        """---
title: Difference-in-Differences
type: topics
tags: [identification, causal]
confidence: high
---

# Difference-in-Differences

DID is a quasi-experimental method for estimating causal effects.

Key assumptions:
- Parallel trends
- No anticipation

Common in labor economics and family firm research.
"""
    )

    methods = wiki / "methods"
    methods.mkdir()
    (methods / "event-study.md").write_text(
        """---
title: Event Study Design
type: methods
tags: [event-study, dynamic]
confidence: medium
---

# Event Study Design

An extension of DID that estimates dynamic treatment effects.
Useful for family business succession timing analysis.
"""
    )

    queries = wiki / "queries"
    queries.mkdir()

    return str(wiki)


class TestSearchWikiPages:
    def test_search_by_keyword(self, sample_wiki):
        results = search_wiki_pages("DID", wiki_root=sample_wiki, limit=5)
        assert len(results) >= 1
        titles = {r["title"] for r in results}
        assert "Difference-in-Differences" in titles

    def test_filter_by_page_type(self, sample_wiki):
        results = search_wiki_pages(
            "effect", wiki_root=sample_wiki, page_types=["methods"]
        )
        assert len(results) >= 1
        for r in results:
            assert r["page_type"] == "methods"

    def test_no_match(self, sample_wiki):
        results = search_wiki_pages("quantum physics", wiki_root=sample_wiki)
        assert results == []

    def test_empty_wiki(self, tmp_path):
        empty = str(tmp_path / "empty_wiki")
        Path(empty).mkdir()
        results = search_wiki_pages("anything", wiki_root=empty)
        assert results == []

    def test_returns_snippets(self, sample_wiki):
        results = search_wiki_pages("parallel trends", wiki_root=sample_wiki)
        assert len(results) >= 1
        assert results[0]["snippet"] != ""

    def test_score_ordering(self, sample_wiki):
        results = search_wiki_pages("family", wiki_root=sample_wiki, limit=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


class TestAnswerFromWiki:
    def test_answer_with_matches(self, sample_wiki):
        result = answer_from_wiki("DID method", wiki_root=sample_wiki)
        assert len(result["pages_used"]) >= 1
        assert "confidence" in result
        assert result["confidence"] in ("low", "medium", "high")

    def test_answer_no_matches(self, sample_wiki):
        result = answer_from_wiki("quantum gravity", wiki_root=sample_wiki)
        assert result["confidence"] == "low"
        assert result["pages_used"] == []

    def test_answer_includes_page_paths(self, sample_wiki):
        result = answer_from_wiki("event study", wiki_root=sample_wiki)
        for page in result["pages_used"]:
            assert "page_path" in page
            assert "title" in page
