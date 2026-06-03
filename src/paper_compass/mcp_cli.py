"""Package-resident MCP CLI entrypoint for paper-compass."""

from __future__ import annotations

import argparse
import json
import sys
import threading

from paper_compass import __version__
from paper_compass.mcp_contracts import list_tools, tool_names
from paper_compass.mcp_server import handle_tool
from paper_compass.runtime_env import ManagedRuntimeError, assert_managed_runtime_active


def _parse_filters(args) -> dict:
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
    print("paper-compass MCP — interactive mode")
    print("Available tools: search_wiki, search_library, ask_research, get_paper_metadata, save_to_wiki, search_passages")
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


def _prewarm_collections(db_path: str = "data/vectordb") -> None:
    import chromadb as _cdb
    from chromadb.config import Settings as _CSet

    try:
        client = _cdb.PersistentClient(path=db_path, settings=_CSet(anonymized_telemetry=False))
    except Exception:
        return

    for prefix in ("wiki", "papers"):
        try:
            for c in client.list_collections():
                if c.name.startswith(prefix + "_") and c.count() > 0:
                    c.get(limit=1, include=["embeddings"])
                    break
        except Exception:
            pass


def mcp_stdio_mode():
    initialized = False

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

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "paper-compass",
                        "version": __version__,
                    },
                    "capabilities": {
                        "tools": {},
                    },
                },
            }
            print(json.dumps(response), flush=True)
            continue

        if method == "notifications/initialized":
            initialized = True
            threading.Thread(target=_prewarm_collections, daemon=True).start()
            continue

        if not initialized:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32002, "message": "Server not initialized"},
            }
            print(json.dumps(response), flush=True)
            continue

        if method == "tools/list":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": list_tools()}}
        elif method == "tools/call":
            tool_name = request.get("params", {}).get("name", "")
            arguments = request.get("params", {}).get("arguments", {})
            try:
                result = handle_tool(tool_name, arguments)
            except Exception as e:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": f"Tool error: {e}"},
                }
                print(json.dumps(response), flush=True)
                continue
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


def main() -> int:
    try:
        assert_managed_runtime_active(context="MCP server")
    except (ManagedRuntimeError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="paper-compass MCP server")
    parser.add_argument("--tool", choices=tool_names(), help="Run a single tool call")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--force-mode", default="auto", choices=["auto", "wiki", "pdf", "hybrid"])
    parser.add_argument("--search-mode", default="semantic", choices=["semantic", "keyword", "hybrid"], help="Passage search mode for search_passages")
    parser.add_argument("--max-sources", type=int, default=5, help="Maximum source papers/snippets for ask_research")
    parser.add_argument("--db-path", default="data/vectordb", help="Path to ChromaDB persistent directory")
    parser.add_argument("--text-dir", default="data/texts", help="Path to extracted text directory")
    parser.add_argument("--library-path", default="data/zotero-export/library.json", help="Path to library.json")
    parser.add_argument("--wiki-root", default="./wiki", help="Wiki root directory for save_to_wiki")
    parser.add_argument("--id-or-doi", help="Paper identifier (doc_id or DOI)")
    parser.add_argument("--title", help="Wiki page title (for save_to_wiki)")
    parser.add_argument("--content", help="Wiki page content (for save_to_wiki)")
    parser.add_argument("--type", dest="page_type", default="queries", choices=["queries", "topics", "methods", "comparisons"])
    parser.add_argument("--confidence", default="medium", choices=["high", "medium", "low"])
    parser.add_argument("--tag", action="append", default=[], help="Tags (repeatable)")
    parser.add_argument("--source", action="append", default=[], help="Source refs (repeatable)")
    parser.add_argument("--filter-collections", action="append", help="Filter by collection")
    parser.add_argument("--filter-tags", action="append", help="Filter by tag")
    parser.add_argument("--filter-authors", action="append", help="Filter by author")
    parser.add_argument("--filter-year-from", type=int, help="Filter by minimum year")
    parser.add_argument("--filter-year-to", type=int, help="Filter by maximum year")
    parser.add_argument("--interactive", action="store_true", help="Interactive tool shell")
    parser.add_argument("--mcp", action="store_true", help="Run MCP JSON-RPC server over stdio")
    args = parser.parse_args()

    if args.mcp:
        mcp_stdio_mode()
        return 0

    if args.interactive:
        interactive_mode()
        return 0

    if not args.tool:
        parser.print_help()
        return 0

    params = {}
    if args.query:
        params["query"] = args.query
    if args.limit:
        params["limit"] = args.limit
    if args.force_mode:
        params["force_mode"] = args.force_mode
    if args.search_mode:
        params["search_mode"] = args.search_mode
    if args.max_sources is not None:
        params["max_sources"] = args.max_sources
    if args.db_path:
        params["db_path"] = args.db_path
    if args.text_dir:
        params["text_dir"] = args.text_dir
    if args.library_path:
        params["library_path"] = args.library_path
    if args.wiki_root:
        params["wiki_root"] = args.wiki_root
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
