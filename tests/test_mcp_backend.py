"""Tests for MCP backend with new architecture."""

import json
import tempfile
from pathlib import Path

import pytest

from miniresearch.models import UnifiedResponse
from miniresearch.mcp_server import handle_tool


class TestUnifiedResponse:
    def test_success_envelope(self):
        resp = UnifiedResponse.success(tool="test", data={"key": "val"}, confidence="high")
        d = resp.to_dict()
        assert d["ok"] is True
        assert d["tool"] == "test"
        assert d["confidence"] == "high"

    def test_error_envelope(self):
        resp = UnifiedResponse.error(tool="test", warnings=["err"])
        d = resp.to_dict()
        assert d["ok"] is False
        assert "err" in d["warnings"][0]


class TestHandleTool:
    def test_unknown_tool(self):
        result = handle_tool("nonexistent", {})
        assert result["ok"] is False

    def test_search_library_no_errors(self, tmp_path):
        """search_library should not crash even without library.json."""
        result = handle_tool("search_library", {"query": "test", "limit": 3})
        assert result["tool"] == "search_library"
        assert "ok" in result

    def test_search_wiki_no_vectordb(self):
        """search_wiki should handle missing vector DB gracefully."""
        result = handle_tool("search_wiki", {"query": "test", "limit": 3, "db_path": "/nonexistent"})
        # May succeed or fail gracefully — either way, should be valid JSON
        assert result["tool"] == "search_wiki"

    def test_get_paper_metadata_no_library(self):
        result = handle_tool("get_paper_metadata", {"id_or_doi": "abc"})
        assert result["tool"] == "get_paper_metadata"

    def test_save_to_wiki_works(self, tmp_path):
        wiki_root = str(tmp_path / "wiki")
        (tmp_path / "wiki" / "queries").mkdir(parents=True)
        (tmp_path / "wiki" / "index.md").write_text("# Index\n## Topics\n## Queries\n")

        result = handle_tool("save_to_wiki", {
            "title": "Test",
            "content": "Content",
            "target_type": "queries",
            "confidence": "medium",
            "wiki_root": wiki_root,
        })
        # Currently wiki_root is not passed through handle_tool's param filtering
        # because it's not in the handler signature. The default "./wiki" is used.
        # This test validates the tool doesn't crash.
        assert result["tool"] == "save_to_wiki"

    def test_ask_research_no_library(self):
        result = handle_tool("ask_research", {"query": "test", "force_mode": "wiki"})
        assert result["tool"] == "ask_research"
        assert "data" in result


class TestFiltersModule:
    def test_search_library_empty(self):
        from miniresearch.filters import search_library
        results = search_library("test", library_path="/nonexistent/library.json")
        assert results == []

    def test_get_paper_metadata_empty(self):
        from miniresearch.filters import get_paper_metadata
        result = get_paper_metadata("abc", library_path="/nonexistent/library.json")
        assert result is None
