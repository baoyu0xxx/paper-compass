"""Tests for filters, models, router, and MCP server modules."""

import json
import tempfile
from pathlib import Path

import pytest

from miniresearch.models import UnifiedResponse, LibraryMatch, PaperDetail, ModeDecision
from miniresearch.filters import search_library, get_paper_metadata, load_library
from miniresearch.router import ask_research, _should_escalate_to_pdf
from miniresearch.mcp_server import handle_tool


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_library(tmp_path):
    """Create a sample library.json for testing."""
    data = [
        {
            "doc_id": "abc123",
            "title": "Family Businesses in China",
            "doi": "10.1234/fbc",
            "authors": ["Zhang", "Li"],
            "year": 2022,
            "journal": "Journal of Management",
            "collections": ["family_firm", "china"],
            "tags": ["did", "labor"],
            "pdf_path": "/tmp/paper_a.pdf",
            "relative_path": "paper_a.pdf",
            "file_name": "paper_a.pdf",
            "metadata_source": "external_csv",
        },
        {
            "doc_id": "def456",
            "title": "Labor Adjustment Dynamics",
            "doi": "10.5678/lad",
            "authors": ["Wang"],
            "year": 2020,
            "journal": "Labor Economics",
            "collections": ["labor"],
            "tags": ["did"],
            "pdf_path": "/tmp/paper_b.pdf",
            "relative_path": "paper_b.pdf",
            "file_name": "paper_b.pdf",
            "metadata_source": "external_csv",
        },
        {
            "doc_id": "ghi789",
            "title": "Unknown Paper",
            "doi": "",
            "authors": [],
            "year": None,
            "journal": "",
            "collections": [],
            "tags": [],
            "pdf_path": "/tmp/paper_c.pdf",
            "relative_path": "paper_c.pdf",
            "file_name": "paper_c.pdf",
            "metadata_source": "scan_only",
        },
    ]
    lib_path = tmp_path / "library.json"
    lib_path.write_text(json.dumps(data))
    return str(lib_path)


# ── models ────────────────────────────────────────────────────────────────────

class TestUnifiedResponse:
    def test_success_creates_correct_envelope(self):
        resp = UnifiedResponse.success(
            tool="search_wiki",
            data={"matches": []},
            mode_used="wiki",
            confidence="high",
        )
        d = resp.to_dict()
        assert d["ok"] is True
        assert d["tool"] == "search_wiki"
        assert d["mode_used"] == "wiki"
        assert d["confidence"] == "high"
        assert len(d["trace_id"]) > 0

    def test_error_creates_correct_envelope(self):
        resp = UnifiedResponse.error(
            tool="search_wiki",
            warnings=["Index not found"],
            next_action="Rebuild index",
        )
        d = resp.to_dict()
        assert d["ok"] is False
        assert d["confidence"] == "low"
        assert d["warnings"] == ["Index not found"]

    def test_to_dict_is_json_serializable(self):
        resp = UnifiedResponse.success(tool="test", data={"key": "value"})
        json.dumps(resp.to_dict())  # should not raise


class TestLibraryMatch:
    def test_defaults(self):
        m = LibraryMatch(doc_id="abc", title="Test")
        assert m.authors == []
        assert m.score == 0.0


class TestPaperDetail:
    def test_defaults(self):
        p = PaperDetail(doc_id="abc", title="Test")
        assert p.authors == []
        assert p.metadata_source == ""


# ── filters ───────────────────────────────────────────────────────────────────

class TestSearchLibrary:
    def test_search_by_title(self, sample_library):
        results = search_library("Family Businesses", library_path=sample_library)
        assert len(results) >= 1
        assert results[0].title == "Family Businesses in China"

    def test_search_no_match(self, sample_library):
        results = search_library("quantum physics", library_path=sample_library)
        assert results == []

    def test_filter_by_collection(self, sample_library):
        results = search_library(
            "family",
            library_path=sample_library,
            filters={"collections": ["family_firm"]},
        )
        assert len(results) >= 1
        assert "family_firm" in results[0].collections

    def test_filter_by_year_range(self, sample_library):
        results = search_library(
            "labor",
            library_path=sample_library,
            filters={"year_from": 2021},
        )
        assert len(results) >= 1
        for r in results:
            assert r.year is None or r.year >= 2021

    def test_empty_library(self, tmp_path):
        results = search_library("anything", library_path=str(tmp_path / "nonexistent.json"))
        assert results == []


class TestGetPaperMetadata:
    def test_lookup_by_doc_id(self, sample_library):
        paper = get_paper_metadata("abc123", library_path=sample_library)
        assert paper is not None
        assert paper.title == "Family Businesses in China"

    def test_lookup_by_doi(self, sample_library):
        paper = get_paper_metadata("10.5678/lad", library_path=sample_library)
        assert paper is not None
        assert paper.title == "Labor Adjustment Dynamics"

    def test_lookup_not_found(self, sample_library):
        paper = get_paper_metadata("nonexistent", library_path=sample_library)
        assert paper is None


# ── router ────────────────────────────────────────────────────────────────────

class TestShouldEscalate:
    def test_detail_triggers_escalation(self):
        decision = _should_escalate_to_pdf(
            "What is the exact identification strategy used in the paper?",
            "medium", 2,
        )
        assert decision.actual in ("hybrid", "pdf")

    def test_low_confidence_escalates(self):
        decision = _should_escalate_to_pdf(
            "family firm governance",
            "low", 0,
        )
        assert decision.actual in ("pdf", "hybrid")

    def test_good_wiki_stays_wiki(self):
        decision = _should_escalate_to_pdf(
            "What is DID?",
            "high", 3,
        )
        assert decision.actual == "wiki"


# ── MCP handle_tool ───────────────────────────────────────────────────────────

class TestHandleTool:
    def test_unknown_tool(self):
        result = handle_tool("nonexistent_tool", {})
        assert result["ok"] is False
        assert "Unknown tool" in str(result["warnings"])

    def test_search_wiki_returns_envelope(self):
        result = handle_tool("search_wiki", {"query": "DID test"})
        assert "ok" in result
        assert result["tool"] == "search_wiki"
        assert "data" in result

    def test_search_library_returns_envelope(self, sample_library):
        # This will use the real config which may not find library.json.
        # Test that the tool handler doesn't crash.
        result = handle_tool("search_library", {"query": "test"})
        assert result["tool"] == "search_library"

    def test_get_paper_metadata_returns_envelope(self):
        result = handle_tool("get_paper_metadata", {"id_or_doi": "abc123"})
        assert result["tool"] == "get_paper_metadata"

    def test_save_to_wiki_returns_envelope(self, tmp_path):
        result = handle_tool("save_to_wiki", {
            "title": "Test Save",
            "content": "Some content",
            "target_type": "queries",
            "confidence": "medium",
        })
        assert result["tool"] == "save_to_wiki"

    def test_ask_research_returns_envelope(self):
        result = handle_tool("ask_research", {
            "query": "What is DID?",
            "force_mode": "wiki",
        })
        assert result["tool"] == "ask_research"
        assert "data" in result
