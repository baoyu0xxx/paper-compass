"""Tests for MCP tool schemas, handler behavior, and UnifiedResponse."""

import json
import tempfile
from pathlib import Path

import pytest

from paper_compass.mcp_contracts import accepted_params, get_tool_contract, list_tools, required_params
from paper_compass.mcp_server import handle_tool
from paper_compass.types import UnifiedResponse


# ── Contract tests (from test_mcp_contract.py) ─────────────────────────


class TestContract:
    def test_tools_list_contains_expected_tools(self):
        names = [t["name"] for t in list_tools()]
        assert names == [
            "ask_research",
            "search_library",
            "search_passages",
            "get_paper_metadata",
            "get_passage_context",
            "get_wiki_page_section",
            "save_to_wiki",
        ]

    def test_search_wiki_is_not_in_default_public_tool_list(self):
        names = [t["name"] for t in list_tools()]
        assert "search_wiki" not in names

    def test_search_wiki_schema_no_unsupported_fields(self):
        tool = get_tool_contract("search_wiki")
        props = set(tool["inputSchema"]["properties"].keys())
        assert "page_types" not in props
        assert "return_snippets" not in props

    def test_save_to_wiki_supports_two_phase_writeback_fields(self):
        params = accepted_params("save_to_wiki")
        assert "dry_run" in params
        assert "commit" in params
        assert "upsert_mode" in params

    def test_get_passage_context_and_wiki_section_tools_are_declared(self):
        names = [t["name"] for t in list_tools()]
        assert "get_passage_context" in names
        assert "get_wiki_page_section" in names

    def test_required_params_are_driven_by_contract_schema(self):
        assert required_params("search_library") == ["query"]
        assert required_params("get_paper_metadata") == []
        assert required_params("get_passage_context") == ["passage_handle"]
        assert required_params("get_wiki_page_section") == ["wiki_handle"]
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

    def test_get_passage_context_requires_passage_handle(self):
        result = handle_tool("get_passage_context", {})
        assert result["ok"] is False

    def test_get_wiki_page_section_requires_wiki_handle(self):
        result = handle_tool("get_wiki_page_section", {})
        assert result["ok"] is False

    def test_search_library_uses_project_root_default_library_when_cwd_differs(self, tmp_path, monkeypatch):
        from paper_compass import search as search_module

        library_path = tmp_path / "library.json"
        library_path.write_text(
            json.dumps(
                [
                    {
                        "key": "ABC123",
                        "title": "Family Firm Succession and Labor Structure",
                        "authors": ["Author"],
                        "year": 2024,
                        "doi": "",
                        "collections": ["family"],
                        "tags": ["succession"],
                        "pdf_path": "dummy.pdf",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(search_module, "DEFAULT_LIBRARY_PATH", library_path)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        result = handle_tool("search_library", {"query": "family", "limit": 3})

        assert result["ok"] is True
        assert result["data"]["matches"][0]["doc_id"] == "ABC123"

    def test_search_library_no_errors(self, tmp_path):
        """search_library should not crash even without library.json."""
        result = handle_tool("search_library", {"query": "test", "limit": 3})
        assert result["tool"] == "search_library"
        assert "ok" in result

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

    def test_save_to_wiki_dry_run_preview(self, tmp_path, monkeypatch):
        wiki_root = str(tmp_path / "wiki")
        (tmp_path / "wiki" / "queries").mkdir(parents=True)
        (tmp_path / "wiki" / "index.md").write_text(
            "# Index\n## Topics\n## Queries\n"
        )
        monkeypatch.setattr("paper_compass.mcp_server.DEFAULT_WIKI_ROOT", tmp_path / "wiki")

        result = handle_tool(
            "save_to_wiki",
            {
                "title": "Test",
                "content": "Content",
                "target_type": "queries",
                "confidence": "medium",
                "dry_run": True,
            },
        )
        assert result["tool"] == "save_to_wiki"
        assert result["ok"] is True
        assert result["data"]["dry_run"] is True
        assert result["data"]["would_write"] is True
        assert result["data"]["page_path"].startswith(wiki_root)

    def test_save_to_wiki_commit_respects_explicit_wiki_root(self, tmp_path):
        wiki_root = tmp_path / "alt-wiki"
        (wiki_root / "queries").mkdir(parents=True)
        (wiki_root / "index.md").write_text("# Index\n## Topics\n## Queries\n", encoding="utf-8")

        result = handle_tool(
            "save_to_wiki",
            {
                "title": "Explicit Root",
                "content": "Committed content",
                "target_type": "queries",
                "confidence": "medium",
                "dry_run": False,
                "commit": True,
                "wiki_root": str(wiki_root),
            },
        )

        assert result["ok"] is True
        assert result["data"]["dry_run"] is False
        page_path = Path(result["data"]["page_path"])
        assert page_path.exists()
        assert str(page_path).startswith(str(wiki_root))
        assert "Committed content" in page_path.read_text(encoding="utf-8")

    def test_save_to_wiki_create_mode_rejects_slug_conflict(self, tmp_path):
        wiki_root = tmp_path / "alt-wiki"
        target_dir = wiki_root / "queries"
        target_dir.mkdir(parents=True)
        (wiki_root / "index.md").write_text("# Index\n## Topics\n## Queries\n", encoding="utf-8")
        (target_dir / "2026-01-01-conflict-title.md").write_text("existing", encoding="utf-8")

        result = handle_tool(
            "save_to_wiki",
            {
                "title": "Conflict Title",
                "content": "Committed content",
                "target_type": "queries",
                "confidence": "medium",
                "dry_run": False,
                "commit": True,
                "wiki_root": str(wiki_root),
            },
        )

        assert result["ok"] is False
        assert any("conflict" in warning.lower() for warning in result["warnings"])

    def test_ask_research_no_library(self):
        result = handle_tool(
            "ask_research", {"query": "test", "force_mode": "wiki"}
        )
        assert result["tool"] == "ask_research"
        assert "data" in result
