"""Contract tests for MCP tool schemas and handler behavior."""

from miniresearch.mcp_contracts import accepted_params, list_tools, required_params
from miniresearch.mcp_server import handle_tool


def test_tools_list_contains_expected_tools():
    names = [t["name"] for t in list_tools()]
    assert names == [
        "search_wiki",
        "search_library",
        "ask_research",
        "get_paper_metadata",
        "search_passages",
        "save_to_wiki",
    ]


def test_search_wiki_schema_no_unsupported_fields():
    tool = next(t for t in list_tools() if t["name"] == "search_wiki")
    props = set(tool["inputSchema"]["properties"].keys())
    assert "page_types" not in props
    assert "return_snippets" not in props


def test_save_to_wiki_accepts_wiki_root():
    params = accepted_params("save_to_wiki")
    assert "wiki_root" in params


def test_required_params_are_driven_by_contract_schema():
    assert required_params("search_library") == ["query"]
    assert required_params("get_paper_metadata") == ["id_or_doi"]
    assert required_params("save_to_wiki") == ["title", "content"]


def test_missing_required_arguments_returns_normalized_error():
    result = handle_tool("search_library", {})
    assert result["ok"] is False
    assert result["tool"] == "search_library"
    assert result["trace_id"]
    assert isinstance(result["warnings"], list)
