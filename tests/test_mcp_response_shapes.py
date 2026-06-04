"""Tests for compact MCP response shaping and drill-down helpers."""

from __future__ import annotations

from pathlib import Path

from paper_compass.mcp_server import handle_tool


def test_search_library_returns_compact_paper_candidates(monkeypatch):
    monkeypatch.setattr(
        "paper_compass.mcp_server.search_library",
        lambda query, filters=None, limit=10: [
            {
                "doc_id": "ABC123",
                "title": "Family Firm Succession and Labor Structure",
                "authors": ["Author A", "Author B"],
                "year": 2024,
                "doi": "10.1000/example",
                "collections": ["family"],
                "tags": ["succession"],
                "pdf_path": "dummy.pdf",
                "metadata_source": "sqlite",
                "score": 8.2,
            }
        ],
    )

    result = handle_tool("search_library", {"query": "family"})

    assert result["ok"] is True
    match = result["data"]["matches"][0]
    assert match["paper_handle"] == "paper:ABC123"
    assert set(match.keys()) == {"paper_handle", "doc_id", "title", "year", "authors", "score"}


def test_search_passages_returns_handle_and_snippet_without_full_passage(monkeypatch):
    monkeypatch.setattr(
        "paper_compass.mcp_server.search_passages",
        lambda query, search_mode="semantic", limit=10, filters=None, db_path=None, text_dir=None, library_path=None: [
            {
                "doc_id": "ABC123",
                "title": "Family Firm Succession and Labor Structure",
                "authors": ["Author A"],
                "year": 2024,
                "doi": "10.1000/example",
                "passage": "This paragraph explains how labor structure changed after succession.",
                "page_num": 12,
                "score": 0.83,
                "search_mode": "hybrid",
                "match_type": "vector",
                "collections": ["family"],
                "tags": ["succession"],
            }
        ],
    )

    result = handle_tool("search_passages", {"query": "labor structure", "search_mode": "hybrid"})

    assert result["ok"] is True
    match = result["data"]["matches"][0]
    assert match["paper_handle"] == "paper:ABC123"
    assert match["passage_handle"] == "passage:ABC123:p12:hybrid:0"
    assert match["snippet"].startswith("This paragraph explains")
    assert "passage" not in match


def test_ask_research_returns_compact_evidence_digest(monkeypatch):
    monkeypatch.setattr(
        "paper_compass.mcp_server.ask_research",
        lambda query, force_mode="auto", filters=None, max_sources=5, db_path=None: {
            "answer": "Succession is associated with a shift toward higher-skill labor.",
            "mode_decision": {"requested": "auto", "actual": "hybrid", "reason": "Detail triggers: evidence"},
            "wiki_context": {
                "pages_used": [
                    {
                        "title": "家族企业代际传承",
                        "page_path": "D:/repo/wiki/topics/family-succession.md",
                        "page_type": "topics",
                        "section": "mechanism",
                    }
                ]
            },
            "pdf_context": {
                "docs_used": [{"doc_id": "ABC123", "title": "Family Firm Succession and Labor Structure", "year": 2024}],
                "evidence_snippets": [
                    {
                        "doc_id": "ABC123",
                        "title": "Family Firm Succession and Labor Structure",
                        "page_num": 12,
                        "passage": "Detailed evidence paragraph.",
                    }
                ],
            },
            "sources": [
                {"source_type": "wiki_page", "id": "D:/repo/wiki/topics/family-succession.md", "title": "家族企业代际传承"},
                {"source_type": "pdf_doc", "id": "ABC123", "title": "Family Firm Succession and Labor Structure"},
            ],
        },
    )

    result = handle_tool("ask_research", {"query": "How does succession affect labor structure?"})

    assert result["ok"] is True
    data = result["data"]
    assert data["answer"].startswith("Succession is associated")
    assert data["mode_decision"]["actual"] == "hybrid"
    assert "evidence_digest" in data
    assert "wiki_context" not in data
    assert "pdf_context" not in data
    assert data["evidence_digest"][0]["source_type"] == "wiki_page"
    assert data["evidence_digest"][1]["paper_handle"] == "paper:ABC123"


def test_get_wiki_page_section_reads_requested_section(tmp_path):
    wiki_file = tmp_path / "family-succession.md"
    wiki_file.write_text(
        "# 家族企业代际传承\n\n## mechanism\nmechanism details\n\n## evidence\nevidence details\n",
        encoding="utf-8",
    )

    result = handle_tool(
        "get_wiki_page_section",
        {"wiki_handle": f"wiki:{wiki_file}#section=mechanism"},
    )

    assert result["ok"] is True
    assert result["data"]["section"] == "mechanism"
    assert "mechanism details" in result["data"]["content"]
