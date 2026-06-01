"""Tests for MCP tool schemas, handler behavior, and UnifiedResponse."""

import json
import tempfile
from pathlib import Path

import pytest

from paper_compass.mcp_contracts import accepted_params, list_tools, required_params
from paper_compass.mcp_server import handle_tool
from paper_compass.types import UnifiedResponse


# ── Contract tests (from test_mcp_contract.py) ─────────────────────────


class TestContract:
    def test_tools_list_contains_expected_tools(self):
        names = [t["name"] for t in list_tools()]
        assert names == [
            "search_wiki",
            "search_library",
            "ask_research",
            "get_paper_metadata",
            "search_passages",
            "save_to_wiki",
        ]

    def test_search_wiki_schema_no_unsupported_fields(self):
        tool = next(t for t in list_tools() if t["name"] == "search_wiki")
        props = set(tool["inputSchema"]["properties"].keys())
        assert "page_types" not in props
        assert "return_snippets" not in props

    def test_save_to_wiki_accepts_wiki_root(self):
        params = accepted_params("save_to_wiki")
        assert "wiki_root" in params

    def test_required_params_are_driven_by_contract_schema(self):
        assert required_params("search_library") == ["query"]
        assert required_params("get_paper_metadata") == ["id_or_doi"]
        assert required_params("save_to_wiki") == ["title", "content"]

    def test_missing_required_arguments_returns_normalized_error(self):
        result = handle_tool("search_library", {})
        assert result["ok"] is False
        assert result["tool"] == "search_library"
        assert result["trace_id"]
        assert isinstance(result["warnings"], list)


# ── UnifiedResponse tests (from test_mcp_backend.py) ───────────────────


class TestUnifiedResponse:
    def test_success_envelope(self):
        resp = UnifiedResponse.success(
            tool="test", data={"key": "val"}, confidence="high"
        )
        d = resp.to_dict()
        assert d["ok"] is True
        assert d["tool"] == "test"
        assert d["confidence"] == "high"

    def test_error_envelope(self):
        resp = UnifiedResponse.error(tool="test", warnings=["err"])
        d = resp.to_dict()
        assert d["ok"] is False
        assert "err" in d["warnings"][0]


# ── HandleTool tests (from test_mcp_backend.py) ────────────────────────


class TestHandleTool:
    def test_unknown_tool(self):
        result = handle_tool("nonexistent", {})
        assert result["ok"] is False

    def test_search_library_no_errors(self, tmp_path):
        """search_library should not crash even without library.json."""
        result = handle_tool("search_library", {"query": "test", "limit": 3})
        assert result["tool"] == "search_library"
        assert "ok" in result
        if result.get("ok"):
            assert "coverage_status" in result["data"]

    def test_search_library_prefers_sync_guidance_when_local_coverage_missing(self):
        result = handle_tool(
            "search_library",
            {"query": "Feature augmentations for high-dimensional learning", "limit": 5},
        )
        assert result["tool"] == "search_library"
        assert result["ok"] is True
        assert result["data"]["coverage_status"] == "missing_from_library_json"
        assert "library.json" in result["next_suggested_action"] or "sync_zotero" in result["next_suggested_action"]

    def test_search_wiki_no_vectordb(self):
        """search_wiki should handle missing vector DB gracefully."""
        result = handle_tool(
            "search_wiki",
            {"query": "test", "limit": 3, "db_path": "/nonexistent"},
        )
        # May succeed or fail gracefully — either way, should be valid JSON
        assert result["tool"] == "search_wiki"

    def test_get_paper_metadata_no_library(self):
        result = handle_tool("get_paper_metadata", {"id_or_doi": "abc"})
        assert result["tool"] == "get_paper_metadata"

    def test_save_to_wiki_works(self, tmp_path):
        wiki_root = str(tmp_path / "wiki")
        (tmp_path / "wiki" / "queries").mkdir(parents=True)
        (tmp_path / "wiki" / "index.md").write_text(
            "# Index\n## Topics\n## Queries\n"
        )

        result = handle_tool(
            "save_to_wiki",
            {
                "title": "Test",
                "content": "Content",
                "target_type": "queries",
                "confidence": "medium",
                "wiki_root": wiki_root,
            },
        )
        assert result["tool"] == "save_to_wiki"
        assert result["ok"] is True
        assert result["data"]["page_path"].startswith(wiki_root)

    def test_ask_research_no_library(self):
        result = handle_tool(
            "ask_research", {"query": "test", "force_mode": "wiki"}
        )
        assert result["tool"] == "ask_research"
        assert "data" in result
