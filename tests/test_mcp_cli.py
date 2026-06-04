"""Tests for paper-compass MCP entrypoints, shim wrappers, and split helper modules."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import paper_compass.mcp_cli_args as mcp_cli_args
import paper_compass.mcp_entrypoint as mcp_entrypoint
import paper_compass.mcp_interactive as mcp_interactive


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_mcp_server.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_mcp_server", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_split_modules_expose_expected_functions():
    stdio_module = importlib.import_module("paper_compass.mcp_stdio")

    assert callable(mcp_cli_args.build_parser)
    assert callable(mcp_cli_args.build_tool_params)
    assert callable(mcp_interactive.interactive_mode)
    assert callable(mcp_interactive.interactive_banner)
    assert callable(stdio_module.mcp_stdio_mode)


def test_script_wrapper_delegates_to_shared_main():
    module = _load_script_module()
    assert module.main is mcp_entrypoint.main


def test_public_vs_advanced_tool_views():
    public_names = mcp_interactive.public_tool_names()
    advanced_names = mcp_interactive.advanced_tool_names()

    assert "search_wiki" not in public_names
    assert "search_wiki" in advanced_names
    assert "get_passage_context" in public_names
    assert "get_wiki_page_section" in public_names


def test_interactive_banner_matches_public_advanced_split():
    banner = mcp_interactive.interactive_banner()

    assert "Public tools:" in banner
    assert "Advanced tools:" in banner
    assert "get_passage_context" in banner
    assert "get_wiki_page_section" in banner
    assert "search_wiki" in banner


def test_build_tool_params_routes_only_tool_relevant_internal_params():
    args = SimpleNamespace(
        query="代际传承",
        limit=10,
        force_mode="auto",
        search_mode="hybrid",
        max_sources=7,
        db_path="tmp/db",
        text_dir="tmp/texts",
        library_path="tmp/library.json",
        wiki_root="tmp/wiki",
        id_or_doi="DOC1",
        paper_handle="paper:DOC1",
        title="T",
        content="C",
        page_type="queries",
        confidence="medium",
        tag=["t1"],
        source=["s1"],
        filter_collections=None,
        filter_tags=None,
        filter_authors=None,
        filter_year_from=None,
        filter_year_to=None,
        dry_run=False,
        commit=False,
        upsert_mode="create",
        passage_handle="passage:DOC1:p1:hybrid:0",
        wiki_handle="wiki:wiki/topics/demo.md",
        window="paragraph",
        max_chars=1200,
        include_frontmatter=False,
    )

    library_params = mcp_cli_args.build_tool_params("search_library", args)
    assert library_params == {"query": "代际传承", "limit": 10}

    passage_params = mcp_cli_args.build_tool_params("search_passages", args)
    assert passage_params["query"] == "代际传承"
    assert passage_params["db_path"] == "tmp/db"
    assert passage_params["text_dir"] == "tmp/texts"
    assert passage_params["library_path"] == "tmp/library.json"
    assert "wiki_root" not in passage_params

    save_params = mcp_cli_args.build_tool_params("save_to_wiki", args)
    assert save_params["wiki_root"] == "tmp/wiki"
    assert save_params["dry_run"] is True
    assert save_params["commit"] is False


def test_shared_entrypoint_routes_commit_and_paper_handle(monkeypatch, capsys):
    captured = {}

    monkeypatch.setattr(mcp_entrypoint, "assert_managed_runtime_active", lambda *args, **kwargs: None)

    def fake_handle_tool(tool_name, params):
        captured["tool_name"] = tool_name
        captured["params"] = params
        return {"ok": True, "data": {}, "warnings": []}

    monkeypatch.setattr(mcp_entrypoint, "handle_tool", fake_handle_tool)

    rc = mcp_entrypoint.main(
        [
            "--tool",
            "save_to_wiki",
            "--title",
            "研究摘要",
            "--content",
            "待写回内容",
            "--commit",
            "--wiki-root",
            "tmp/wiki",
        ]
    )

    assert rc == 0
    assert captured["tool_name"] == "save_to_wiki"
    assert captured["params"]["commit"] is True
    assert captured["params"]["dry_run"] is False
    assert captured["params"]["wiki_root"] == "tmp/wiki"
    assert '"ok": true' in capsys.readouterr().out

    rc = mcp_entrypoint.main(
        [
            "--tool",
            "get_paper_metadata",
            "--paper-handle",
            "paper:ZOTERO_KEY",
        ]
    )

    assert rc == 0
    assert captured["tool_name"] == "get_paper_metadata"
    assert captured["params"] == {"paper_handle": "paper:ZOTERO_KEY"}


def test_shared_entrypoint_passes_search_passages_extra_params(monkeypatch, capsys):
    captured = {}

    monkeypatch.setattr(mcp_entrypoint, "assert_managed_runtime_active", lambda *args, **kwargs: None)

    def fake_handle_tool(tool_name, params):
        captured["tool_name"] = tool_name
        captured["params"] = params
        return {"ok": True, "data": {"matches": []}, "warnings": []}

    monkeypatch.setattr(mcp_entrypoint, "handle_tool", fake_handle_tool)

    rc = mcp_entrypoint.main(
        [
            "--tool",
            "search_passages",
            "--query",
            "代际传承",
            "--search-mode",
            "keyword",
            "--db-path",
            "tmp/db",
            "--text-dir",
            "tmp/texts",
            "--library-path",
            "tmp/library.json",
        ]
    )

    assert rc == 0
    assert captured["tool_name"] == "search_passages"
    assert captured["params"]["query"] == "代际传承"
    assert captured["params"]["search_mode"] == "keyword"
    assert captured["params"]["db_path"] == "tmp/db"
    assert captured["params"]["text_dir"] == "tmp/texts"
    assert captured["params"]["library_path"] == "tmp/library.json"
    assert '"ok": true' in capsys.readouterr().out


def test_shared_entrypoint_passes_ask_research_extra_params(monkeypatch):
    captured = {}

    monkeypatch.setattr(mcp_entrypoint, "assert_managed_runtime_active", lambda *args, **kwargs: None)

    def fake_handle_tool(tool_name, params):
        captured["tool_name"] = tool_name
        captured["params"] = params
        return {"ok": True, "data": {}, "warnings": []}

    monkeypatch.setattr(mcp_entrypoint, "handle_tool", fake_handle_tool)

    rc = mcp_entrypoint.main(
        [
            "--tool",
            "ask_research",
            "--query",
            "家族企业继承",
            "--max-sources",
            "7",
            "--db-path",
            "tmp/db",
        ]
    )

    assert rc == 0
    assert captured["tool_name"] == "ask_research"
    assert captured["params"]["max_sources"] == 7
    assert captured["params"]["db_path"] == "tmp/db"


def test_parser_help_mentions_new_params(capsys):
    parser = mcp_cli_args.build_parser()
    parser.print_help()
    out = capsys.readouterr().out

    assert "--search-mode" in out
    assert "--db-path" in out
    assert "--text-dir" in out
    assert "--library-path" in out
    assert "--max-sources" in out
    assert "--paper-handle" in out
    assert "--passage-handle" in out
    assert "--wiki-handle" in out
    assert "--commit" in out


def test_shared_entrypoint_fails_fast_on_runtime_mismatch(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise RuntimeError("MCP server runtime error: managed runtime mismatch")

    monkeypatch.setattr(mcp_entrypoint, "assert_managed_runtime_active", fail)

    rc = mcp_entrypoint.main(["--help"])

    assert rc == 1
    assert "managed runtime mismatch" in capsys.readouterr().err
