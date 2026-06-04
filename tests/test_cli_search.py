"""Tests for paper-compass search CLI."""

from __future__ import annotations

import pytest

from paper_compass.cli import main


@pytest.mark.parametrize(
    ("argv", "expected_tool", "expected_params"),
    [
        (
            ["paper-compass", "search", "wiki", "--query", "代际传承", "--db-path", "tmp/db"],
            "search_wiki",
            {"query": "代际传承", "limit": 5, "db_path": "tmp/db"},
        ),
        (
            [
                "paper-compass",
                "search",
                "library",
                "--query",
                "family firm",
                "--filter-tags",
                "succession",
            ],
            "search_library",
            {"query": "family firm", "limit": 10, "filters": {"tags": ["succession"]}},
        ),
        (
            [
                "paper-compass",
                "search",
                "passages",
                "--query",
                "劳动力结构",
                "--search-mode",
                "keyword",
                "--db-path",
                "tmp/db",
                "--text-dir",
                "tmp/texts",
                "--library-path",
                "tmp/library.json",
            ],
            "search_passages",
            {
                "query": "劳动力结构",
                "limit": 10,
                "search_mode": "keyword",
                "db_path": "tmp/db",
                "text_dir": "tmp/texts",
                "library_path": "tmp/library.json",
            },
        ),
        (
            [
                "paper-compass",
                "search",
                "ask",
                "--query",
                "家族企业继承如何影响劳动力结构？",
                "--force-mode",
                "hybrid",
                "--max-sources",
                "7",
            ],
            "ask_research",
            {
                "query": "家族企业继承如何影响劳动力结构？",
                "force_mode": "hybrid",
                "max_sources": 7,
                "db_path": "data/vectordb",
            },
        ),
        (
            [
                "paper-compass",
                "search",
                "passage-context",
                "--passage-handle",
                "passage:ABC123:p12:hybrid:0",
                "--window",
                "section",
            ],
            "get_passage_context",
            {
                "passage_handle": "passage:ABC123:p12:hybrid:0",
                "window": "section",
                "max_chars": 2000,
            },
        ),
        (
            [
                "paper-compass",
                "search",
                "wiki-section",
                "--wiki-handle",
                "wiki:wiki/topics/family-succession.md#section=mechanism",
            ],
            "get_wiki_page_section",
            {
                "wiki_handle": "wiki:wiki/topics/family-succession.md#section=mechanism",
                "include_frontmatter": False,
            },
        ),
    ],
)
def test_search_cli_dispatches_to_expected_tool(monkeypatch, argv, expected_tool, expected_params):
    captured = {}

    def fake_handle_tool(tool_name, params):
        captured["tool_name"] = tool_name
        captured["params"] = params
        return {"ok": True, "data": {"matches": []}, "warnings": []}

    monkeypatch.setattr("paper_compass.cli.search.handle_tool", fake_handle_tool)
    monkeypatch.setattr("sys.argv", argv)

    rc = main()
    assert rc == 0
    assert captured["tool_name"] == expected_tool
    assert captured["params"] == expected_params


def test_search_cli_json_output(monkeypatch, capsys):
    def fake_handle_tool(tool_name, params):
        return {"ok": True, "data": {"matches": [{"title": "A paper"}]}, "warnings": []}

    monkeypatch.setattr("paper_compass.cli.search.handle_tool", fake_handle_tool)
    monkeypatch.setattr(
        "sys.argv",
        ["paper-compass", "search", "--json", "wiki", "--query", "家族企业"],
    )

    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert '"ok": true' in out
    assert '"title": "A paper"' in out


def test_search_cli_text_output_for_passages(monkeypatch, capsys):
    def fake_handle_tool(tool_name, params):
        return {
            "ok": True,
            "data": {
                "matches": [
                    {
                        "title": "Succession Study",
                        "doc_id": "ABC123",
                        "score": 0.88,
                        "page_num": 5,
                        "search_mode": "keyword",
                        "match_type": "fulltext",
                        "passage_handle": "passage:ABC123:p5:keyword:0",
                        "snippet": "This paper studies labor structure changes.",
                    }
                ]
            },
            "warnings": [],
        }

    monkeypatch.setattr("paper_compass.cli.search.handle_tool", fake_handle_tool)
    monkeypatch.setattr(
        "sys.argv",
        ["paper-compass", "search", "passages", "--query", "labor structure"],
    )

    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "search_passages" in out
    assert "Succession Study" in out
    assert "ABC123" in out
    assert "passage:ABC123:p5:keyword:0" in out
    assert "labor structure changes" in out
