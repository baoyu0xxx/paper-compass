"""Single source of truth for MCP tool contracts."""

from __future__ import annotations

from typing import Any, Dict, List


TOOL_CONTRACTS: List[Dict[str, Any]] = [
    {
        "name": "search_wiki",
        "description": "Search the local markdown research wiki",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 5},
                "db_path": {"type": "string", "default": "data/vectordb"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_library",
        "description": "Search the paper library metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": {"type": "object"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ask_research",
        "description": "Answer a research question using wiki + PDF retrieval",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "force_mode": {"type": "string", "enum": ["auto", "wiki", "pdf", "hybrid"]},
                "filters": {"type": "object"},
                "max_sources": {"type": "integer", "default": 5},
                "db_path": {"type": "string", "default": "data/vectordb"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_paper_metadata",
        "description": "Get structured metadata for a single paper",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id_or_doi": {"type": "string"},
            },
            "required": ["id_or_doi"],
        },
    },
    {
        "name": "save_to_wiki",
        "description": "Save curated results to the research wiki",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "target_type": {"type": "string", "enum": ["queries", "topics", "methods", "comparisons"]},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_refs": {"type": "array", "items": {"type": "string"}},
                "tags": {"type": "array", "items": {"type": "string"}},
                "wiki_root": {"type": "string", "default": "./wiki"},
            },
            "required": ["title", "content"],
        },
    },
]


def list_tools() -> List[Dict[str, Any]]:
    return TOOL_CONTRACTS


def get_tool_contract(tool_name: str) -> Dict[str, Any] | None:
    for tool in TOOL_CONTRACTS:
        if tool["name"] == tool_name:
            return tool
    return None


def tool_names() -> List[str]:
    return [tool["name"] for tool in TOOL_CONTRACTS]


def accepted_params(tool_name: str) -> List[str]:
    contract = get_tool_contract(tool_name)
    if contract is None:
        return []
    return list(contract.get("inputSchema", {}).get("properties", {}).keys())


def required_params(tool_name: str) -> List[str]:
    contract = get_tool_contract(tool_name)
    if contract is None:
        return []
    return list(contract.get("inputSchema", {}).get("required", []))
