#!/usr/bin/env python3
"""
MCP server entry point for paper-compass.

Supports two modes:
  1. Tool-call mode:     python scripts/run_mcp_server.py --tool search_wiki --query "DID"
  2. Interactive mode:   python scripts/run_mcp_server.py --interactive
  3. MCP stdio mode:     python scripts/run_mcp_server.py --mcp  (JSON-RPC over stdin/stdout)

Usage:
    # Search wiki
    python scripts/run_mcp_server.py --tool search_wiki --query "difference in differences"

    # Search library with filters
    python scripts/run_mcp_server.py --tool search_library --query "family firm" \\
        --filter-collections family_firm --filter-year-from 2018

    # Ask research question
    python scripts/run_mcp_server.py --tool ask_research --query "How does family \\
        succession affect labor structure?" --force-mode auto

    # Get paper metadata
    python scripts/run_mcp_server.py --tool get_paper_metadata --id-or-doi 10.1234/abc

    # Save to wiki
    python scripts/run_mcp_server.py --tool save_to_wiki --title "DID Findings" \\
        --content "Key result..." --type queries
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from miniresearch.mcp_server import handle_tool


def _parse_filters(args) -> dict:
    """Parse filter arguments from CLI."""
    filters = {}
    if hasattr(args, "filter_collections") and args.filter_collections:
        filters["collections"] = args.filter_collections
    if hasattr(args, "filter_tags") and args.filter_tags:
        filters["tags"] = args.filter_tags
    if hasattr(args, "filter_authors") and args.filter_authors:
        filters["authors"] = args.filter_authors
    if hasattr(args, "filter_year_from") and args.filter_year_from is not None:
        filters["year_from"] = args.filter_year_from
    if hasattr(args, "filter_year_to") and args.filter_year_to is not None:
        filters["year_to"] = args.filter_year_to
    return filters if filters else None


def interactive_mode():
    """Simple interactive prompt for manual tool testing."""
    print("paper-compass MCP — interactive mode")
    print("Available tools: search_wiki, search_library, ask_research, get_paper_metadata, save_to_wiki")
    print("Type 'help' for usage, 'quit' to exit.\n")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            break
        if line.lower() == "help":
            print("  search_wiki <query>")
            print("  search_library <query>")
            print("  ask_research <query>")
            print("  get_paper_metadata <id_or_doi>")
            print("  save_to_wiki <title> | <content>")
            continue

        # Parse: tool_name rest_of_line
        parts = line.split(maxsplit=1)
        tool = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        params = {}
        if tool == "search_wiki":
            params["query"] = rest
            params["limit"] = 5
        elif tool == "search_library":
            params["query"] = rest
            params["limit"] = 10
        elif tool == "ask_research":
            params["query"] = rest
            params["force_mode"] = "auto"
        elif tool == "get_paper_metadata":
            params["id_or_doi"] = rest
        elif tool == "save_to_wiki":
            if "|" in rest:
                title_part, content_part = rest.split("|", 1)
                params["title"] = title_part.strip()
                params["content"] = content_part.strip()
            else:
                print("  Usage: save_to_wiki <title> | <content>")
                continue
        else:
            print(f"  Unknown tool: {tool}")
            continue

        result = handle_tool(tool, params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()


def mcp_stdio_mode():
    """Minimal MCP JSON-RPC stdio server (stub — expand as needed)."""
    import json

    # Send initialization response
    init_response = {
        "jsonrpc": "2.0",
        "id": 0,
        "result": {
            "serverInfo": {
                "name": "paper-compass",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {},
            },
        },
    }
    print(json.dumps(init_response), flush=True)

    # Simple request loop
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method", "")
        req_id = request.get("id")

        if method == "tools/list":
            tools = [
                {
                    "name": "search_wiki",
                    "description": "Search the local markdown research wiki",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {"type": "integer", "default": 5},
                            "page_types": {"type": "array", "items": {"type": "string"}},
                            "return_snippets": {"type": "boolean", "default": True},
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
                        },
                        "required": ["title", "content"],
                    },
                },
            ]
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

        elif method == "tools/call":
            tool_name = request.get("params", {}).get("name", "")
            arguments = request.get("params", {}).get("arguments", {})
            result = handle_tool(tool_name, arguments)
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]},
            }

        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        print(json.dumps(response), flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="paper-compass MCP server"
    )
    parser.add_argument(
        "--tool",
        choices=["search_wiki", "search_library", "ask_research", "get_paper_metadata", "save_to_wiki"],
        help="Run a single tool call",
    )
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--force-mode", default="auto", choices=["auto", "wiki", "pdf", "hybrid"])
    parser.add_argument("--id-or-doi", help="Paper identifier (doc_id or DOI)")
    parser.add_argument("--title", help="Wiki page title (for save_to_wiki)")
    parser.add_argument("--content", help="Wiki page content (for save_to_wiki)")
    parser.add_argument("--type", dest="page_type", default="queries",
                        choices=["queries", "topics", "methods", "comparisons"])
    parser.add_argument("--confidence", default="medium", choices=["high", "medium", "low"])
    parser.add_argument("--tag", action="append", default=[], help="Tags (repeatable)")
    parser.add_argument("--source", action="append", default=[], help="Source refs (repeatable)")
    parser.add_argument("--filter-collections", action="append", help="Filter by collection")
    parser.add_argument("--filter-tags", action="append", help="Filter by tag")
    parser.add_argument("--filter-authors", action="append", help="Filter by author")
    parser.add_argument("--filter-year-from", type=int)
    parser.add_argument("--filter-year-to", type=int)
    parser.add_argument("--interactive", action="store_true", help="Interactive prompt mode")
    parser.add_argument("--mcp", action="store_true", help="MCP JSON-RPC stdio mode")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    if args.mcp:
        mcp_stdio_mode()
        return

    if not args.tool:
        parser.print_help()
        return

    # Build params for the specified tool
    params = {}
    if args.query:
        params["query"] = args.query
    if args.limit:
        params["limit"] = args.limit
    if args.force_mode:
        params["force_mode"] = args.force_mode
    if args.id_or_doi:
        params["id_or_doi"] = args.id_or_doi
    if args.title:
        params["title"] = args.title
    if args.content:
        params["content"] = args.content
    if args.page_type:
        params["target_type"] = args.page_type
    if args.confidence:
        params["confidence"] = args.confidence
    if args.tag:
        params["tags"] = args.tag
    if args.source:
        params["source_refs"] = args.source

    filters = _parse_filters(args)
    if filters:
        params["filters"] = filters

    result = handle_tool(args.tool, params)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
