"""Single source of truth for MCP tool contracts."""

from __future__ import annotations

from typing import Any, Dict, List


_FILTER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "authors": {"type": "array", "items": {"type": "string"}},
        "collections": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "year_from": {"type": "integer"},
        "year_to": {"type": "integer"},
    },
    "additionalProperties": False,
}


_ALL_TOOL_CONTRACTS: List[Dict[str, Any]] = [
    {
        "name": "search_wiki",
        "visibility": "advanced",
        "description": "Advanced wiki-index search. Prefer ask_research for broad questions and get_wiki_page_section for reading a cited wiki section.",
        "internalProperties": {
            "db_path": {"type": "string", "default": "data/vectordb"}
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ask_research",
        "visibility": "public",
        "description": "Answer a research question using wiki knowledge plus PDF evidence. Use this for broad or synthesized questions, not for reading a specific passage verbatim.",
        "internalProperties": {
            "db_path": {"type": "string", "default": "data/vectordb"}
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "force_mode": {"type": "string", "enum": ["auto", "wiki", "pdf", "hybrid"]},
                "filters": _FILTER_SCHEMA,
                "max_sources": {"type": "integer", "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_library",
        "visibility": "public",
        "description": "Search the paper library for candidate papers by topic, author, collection, tag, or year filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": _FILTER_SCHEMA,
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_passages",
        "visibility": "public",
        "description": "Locate original text evidence snippets from papers. Use get_passage_context afterwards to expand a specific hit.",
        "internalProperties": {
            "db_path": {"type": "string", "default": "data/vectordb"},
            "text_dir": {"type": "string", "default": "data/texts"},
            "library_path": {"type": "string", "default": "data/zotero-export/library.json"}
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword or short phrase to search for"},
                "search_mode": {"type": "string", "enum": ["semantic", "keyword", "hybrid"], "default": "semantic"},
                "limit": {"type": "integer", "default": 10},
                "filters": _FILTER_SCHEMA,
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_paper_metadata",
        "visibility": "public",
        "description": "Get structured metadata for a single paper by paper_handle, Zotero key/doc_id, DOI, or exact title.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paper_handle": {"type": "string"},
                "id_or_doi": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_passage_context",
        "visibility": "public",
        "description": "Expand a previously returned passage_handle into a longer paragraph or section context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "passage_handle": {"type": "string"},
                "window": {"type": "string", "enum": ["match_only", "paragraph", "section", "page"], "default": "paragraph"},
                "max_chars": {"type": "integer", "default": 2000},
            },
            "required": ["passage_handle"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_wiki_page_section",
        "visibility": "public",
        "description": "Read the full content of a wiki page or a specific wiki section previously referenced by a wiki_handle.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "wiki_handle": {"type": "string"},
                "include_frontmatter": {"type": "boolean", "default": False},
            },
            "required": ["wiki_handle"],
            "additionalProperties": False,
        },
    },
    {
        "name": "save_to_wiki",
        "visibility": "public",
        "description": "Preview or commit a curated writeback into the research wiki. Defaults to dry-run preview; set commit=true to write.",
        "internalProperties": {
            "wiki_root": {"type": "string", "default": "./wiki"}
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "target_type": {"type": "string", "enum": ["queries", "topics", "methods", "comparisons"]},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_refs": {"type": "array", "items": {"type": "string"}},
                "tags": {"type": "array", "items": {"type": "string"}},
                "dry_run": {"type": "boolean", "default": True},
                "commit": {"type": "boolean", "default": False},
                "upsert_mode": {"type": "string", "enum": ["create", "replace_if_same_slug", "merge"], "default": "create"},
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        },
    },
]


def list_tools(visibility: str = "public") -> List[Dict[str, Any]]:
    if visibility == "all":
        return _ALL_TOOL_CONTRACTS
    return [tool for tool in _ALL_TOOL_CONTRACTS if tool.get("visibility", "public") == visibility]


def get_tool_contract(tool_name: str) -> Dict[str, Any] | None:
    for tool in _ALL_TOOL_CONTRACTS:
        if tool["name"] == tool_name:
            return tool
    return None


def tool_names(include_advanced: bool = True) -> List[str]:
    tools = _ALL_TOOL_CONTRACTS if include_advanced else list_tools()
    return [tool["name"] for tool in tools]


def accepted_params(tool_name: str) -> List[str]:
    contract = get_tool_contract(tool_name)
    if contract is None:
        return []
    names = list(contract.get("inputSchema", {}).get("properties", {}).keys())
    names.extend(contract.get("internalProperties", {}).keys())
    return names


def required_params(tool_name: str) -> List[str]:
    contract = get_tool_contract(tool_name)
    if contract is None:
        return []
    return list(contract.get("inputSchema", {}).get("required", []))


def param_schema(tool_name: str, param_name: str) -> Dict[str, Any] | None:
    contract = get_tool_contract(tool_name)
    if contract is None:
        return None
    schema = contract.get("inputSchema", {}).get("properties", {}).get(param_name)
    if schema is not None:
        return schema
    return contract.get("internalProperties", {}).get(param_name)
