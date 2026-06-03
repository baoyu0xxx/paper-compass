"""Tests for paper-compass MCP CLI wrappers and script wrapper parity."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from paper_compass import mcp_cli


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_mcp_server.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_mcp_server", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_package_mcp_cli_passes_search_passages_extra_params(monkeypatch, capsys):
    captured = {}

    monkeypatch.setattr(mcp_cli, "assert_managed_runtime_active", lambda *args, **kwargs: None)

    def fake_handle_tool(tool_name, params):
        captured["tool_name"] = tool_name
        captured["params"] = params
        return {"ok": True, "data": {"matches": []}, "warnings": []}

    monkeypatch.setattr(mcp_cli, "handle_tool", fake_handle_tool)
    monkeypatch.setattr(
        "sys.argv",
        [
            "paper-compass-mcp",
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
        ],
    )

    rc = mcp_cli.main()
    assert rc == 0
    assert captured["tool_name"] == "search_passages"
    assert captured["params"]["query"] == "代际传承"
    assert captured["params"]["search_mode"] == "keyword"
    assert captured["params"]["db_path"] == "tmp/db"
    assert captured["params"]["text_dir"] == "tmp/texts"
    assert captured["params"]["library_path"] == "tmp/library.json"
    assert '"ok": true' in capsys.readouterr().out


def test_package_mcp_cli_passes_ask_research_extra_params(monkeypatch):
    captured = {}

    monkeypatch.setattr(mcp_cli, "assert_managed_runtime_active", lambda *args, **kwargs: None)

    def fake_handle_tool(tool_name, params):
        captured["tool_name"] = tool_name
        captured["params"] = params
        return {"ok": True, "data": {}, "warnings": []}

    monkeypatch.setattr(mcp_cli, "handle_tool", fake_handle_tool)
    monkeypatch.setattr(
        "sys.argv",
        [
            "paper-compass-mcp",
            "--tool",
            "ask_research",
            "--query",
            "家族企业继承",
            "--max-sources",
            "7",
            "--db-path",
            "tmp/db",
        ],
    )

    rc = mcp_cli.main()
    assert rc == 0
    assert captured["tool_name"] == "ask_research"
    assert captured["params"]["max_sources"] == 7
    assert captured["params"]["db_path"] == "tmp/db"


def test_script_wrapper_accepts_new_args_and_forwards(monkeypatch, capsys):
    module = _load_script_module()
    captured = {}

    monkeypatch.setattr(module, "assert_managed_runtime_active", lambda *args, **kwargs: None)

    def fake_handle_tool(tool_name, params):
        captured["tool_name"] = tool_name
        captured["params"] = params
        return {"ok": True, "data": {"matches": []}, "warnings": []}

    monkeypatch.setattr(module, "handle_tool", fake_handle_tool)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_mcp_server.py",
            "--tool",
            "search_passages",
            "--query",
            "劳动力结构",
            "--search-mode",
            "hybrid",
            "--db-path",
            "data/custom-db",
            "--text-dir",
            "data/custom-texts",
            "--library-path",
            "data/custom-library.json",
        ],
    )

    module.main()
    assert captured["tool_name"] == "search_passages"
    assert captured["params"]["search_mode"] == "hybrid"
    assert captured["params"]["db_path"] == "data/custom-db"
    assert captured["params"]["text_dir"] == "data/custom-texts"
    assert captured["params"]["library_path"] == "data/custom-library.json"
    assert '"ok": true' in capsys.readouterr().out


def test_script_wrapper_help_mentions_new_params(capsys):
    module = _load_script_module()
    parser = argparse.ArgumentParser(description="paper-compass MCP server")
    parser.add_argument("--tool", choices=module.tool_names(), help="Run a single tool call")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--force-mode", default="auto", choices=["auto", "wiki", "pdf", "hybrid"])
    parser.add_argument("--search-mode", default="semantic", choices=["semantic", "keyword", "hybrid"], help="Passage search mode for search_passages")
    parser.add_argument("--max-sources", type=int, default=5, help="Maximum source papers/snippets for ask_research")
    parser.add_argument("--db-path", default="data/vectordb", help="Path to ChromaDB persistent directory")
    parser.add_argument("--text-dir", default="data/texts", help="Path to extracted text directory")
    parser.add_argument("--library-path", default="data/zotero-export/library.json", help="Path to library.json")
    parser.add_argument("--wiki-root", default="./wiki", help="Wiki root directory for save_to_wiki")
    parser.print_help()
    out = capsys.readouterr().out
    assert "--search-mode" in out
    assert "--db-path" in out
    assert "--text-dir" in out
    assert "--library-path" in out
    assert "--max-sources" in out


def test_package_mcp_cli_fails_fast_on_runtime_mismatch(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise RuntimeError("MCP server runtime error: managed runtime mismatch")

    monkeypatch.setattr(mcp_cli, "assert_managed_runtime_active", fail)
    monkeypatch.setattr("sys.argv", ["paper-compass-mcp", "--help"])

    rc = mcp_cli.main()

    assert rc == 1
    assert "managed runtime mismatch" in capsys.readouterr().err



def test_script_wrapper_fails_fast_on_runtime_mismatch(monkeypatch, capsys):
    module = _load_script_module()

    def fail(*args, **kwargs):
        raise RuntimeError("MCP server runtime error: managed runtime mismatch")

    monkeypatch.setattr(module, "assert_managed_runtime_active", fail)
    monkeypatch.setattr("sys.argv", ["run_mcp_server.py", "--help"])

    rc = module.main()

    assert rc == 1
    assert "managed runtime mismatch" in capsys.readouterr().err
