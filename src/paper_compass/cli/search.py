"""paper-compass search subcommand.

Unified local retrieval entrypoint for wiki, library metadata, passages, and ask_research.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from paper_compass.mcp_server import handle_tool


def _add_common_query_args(parser: argparse.ArgumentParser, *, default_limit: int) -> None:
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--limit", type=int, default=default_limit, help="Maximum results")


def _add_common_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--filter-collections", action="append", help="Filter by collection")
    parser.add_argument("--filter-tags", action="append", help="Filter by tag")
    parser.add_argument("--filter-authors", action="append", help="Filter by author")
    parser.add_argument("--filter-year-from", type=int, help="Filter by minimum year")
    parser.add_argument("--filter-year-to", type=int, help="Filter by maximum year")


def _parse_filters(args: argparse.Namespace) -> dict[str, Any] | None:
    filters: dict[str, Any] = {}
    if getattr(args, "filter_collections", None):
        filters["collections"] = args.filter_collections
    if getattr(args, "filter_tags", None):
        filters["tags"] = args.filter_tags
    if getattr(args, "filter_authors", None):
        filters["authors"] = args.filter_authors
    if getattr(args, "filter_year_from", None) is not None:
        filters["year_from"] = args.filter_year_from
    if getattr(args, "filter_year_to", None) is not None:
        filters["year_to"] = args.filter_year_to
    return filters or None


def _print_json(result: dict[str, Any]) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _format_library_matches(matches: list[dict[str, Any]]) -> None:
    if not matches:
        print("  (no matches)")
        return
    for idx, match in enumerate(matches, 1):
        authors = ", ".join(match.get("authors", [])) or "n.a."
        year = match.get("year") or "n.d."
        print(f"  {idx}. [{match.get('score', 0):.2f}] {match.get('title', '')}")
        print(f"     doc_id: {match.get('doc_id', '')} | year: {year}")
        print(f"     authors: {authors}")


def _format_wiki_matches(matches: list[dict[str, Any]]) -> None:
    if not matches:
        print("  (no matches)")
        return
    for idx, match in enumerate(matches, 1):
        print(f"  {idx}. [{match.get('score', 0):.3f}] {match.get('title', '')}")
        print(f"     page: {match.get('page_path', '')} | section: {match.get('section', '')}")
        snippet = (match.get("snippet", "") or "").strip().replace("\n", " ")
        if snippet:
            print(f"     snippet: {snippet}")


def _format_passage_matches(matches: list[dict[str, Any]]) -> None:
    if not matches:
        print("  (no matches)")
        return
    for idx, match in enumerate(matches, 1):
        page_num = match.get("page_num")
        page_part = f" | p.{page_num}" if page_num is not None else ""
        print(f"  {idx}. [{match.get('score', 0):.3f}] {match.get('title', '')}")
        print(
            f"     doc_id: {match.get('doc_id', '')}{page_part} | mode: {match.get('search_mode', '')} | match: {match.get('match_type', '')}"
        )
        if match.get("passage_handle"):
            print(f"     passage_handle: {match.get('passage_handle', '')}")
        snippet = (match.get("snippet", "") or match.get("passage", "") or "").strip().replace("\n", " ")
        if snippet:
            print(f"     snippet: {snippet[:240]}")


def _format_passage_context(result: dict[str, Any]) -> None:
    data = result.get("data", {})
    print(f"  title: {data.get('title', '')}")
    print(f"  paper_handle: {data.get('paper_handle', '')}")
    print(f"  passage_handle: {data.get('passage_handle', '')}")
    if data.get("page_num") is not None:
        print(f"  page_num: {data.get('page_num')}")
    print()
    text = (data.get("text", "") or "").strip()
    print(text or "  (no text)")


def _format_wiki_section(result: dict[str, Any]) -> None:
    data = result.get("data", {})
    print(f"  title: {data.get('title', '')}")
    print(f"  wiki_handle: {data.get('wiki_handle', '')}")
    if data.get("section"):
        print(f"  section: {data.get('section')}")
    print()
    content = (data.get("content", "") or "").strip()
    print(content or "  (no content)")


def _format_ask_result(result: dict[str, Any]) -> None:
    data = result.get("data", {})
    mode = data.get("mode_decision", {})
    if mode:
        print(
            f"  mode: requested={mode.get('requested', '')} actual={mode.get('actual', '')} | {mode.get('reason', '')}"
        )
        print()
    answer = (data.get("answer", "") or "").strip()
    if answer:
        print(answer)
    else:
        print("  (no answer)")


def _dispatch_and_render(tool_name: str, params: dict[str, Any], output_json: bool) -> int:
    result = handle_tool(tool_name, params)
    if output_json:
        _print_json(result)
        return 0 if result.get("ok") else 1

    if not result.get("ok"):
        print(f"  ✗ {tool_name} failed")
        for warning in result.get("warnings", []):
            print(f"    - {warning}")
        return 1

    print()
    print(f"  {tool_name}")
    print()

    data = result.get("data", {})
    if tool_name == "search_library":
        _format_library_matches(data.get("matches", []))
    elif tool_name == "search_wiki":
        _format_wiki_matches(data.get("matches", []))
    elif tool_name == "search_passages":
        _format_passage_matches(data.get("matches", []))
    elif tool_name == "get_passage_context":
        _format_passage_context(result)
    elif tool_name == "get_wiki_page_section":
        _format_wiki_section(result)
    elif tool_name == "ask_research":
        _format_ask_result(result)
    else:
        _print_json(result)

    for warning in result.get("warnings", []):
        print()
        print(f"  warning: {warning}")

    return 0


def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "search",
        help="Search wiki, library, passages, or ask a research question",
        description="Unified local retrieval CLI for paper-compass.",
    )
    parser.add_argument("--json", action="store_true", help="Print raw JSON output")
    search_subparsers = parser.add_subparsers(dest="search_target", metavar="TARGET")
    search_subparsers.required = True

    wiki_parser = search_subparsers.add_parser("wiki", help="Semantic search over wiki index")
    _add_common_query_args(wiki_parser, default_limit=5)
    wiki_parser.add_argument("--db-path", default="data/vectordb", help="Path to ChromaDB persistent directory")
    wiki_parser.set_defaults(func=execute_search)

    library_parser = search_subparsers.add_parser("library", help="Search library metadata")
    _add_common_query_args(library_parser, default_limit=10)
    _add_common_filter_args(library_parser)
    library_parser.set_defaults(func=execute_search)

    passages_parser = search_subparsers.add_parser("passages", help="Search original text passages")
    _add_common_query_args(passages_parser, default_limit=10)
    _add_common_filter_args(passages_parser)
    passages_parser.add_argument(
        "--search-mode",
        default="semantic",
        choices=["semantic", "keyword", "hybrid"],
        help="Passage search mode",
    )
    passages_parser.add_argument("--db-path", default="data/vectordb", help="Path to ChromaDB persistent directory")
    passages_parser.add_argument("--text-dir", default="data/texts", help="Path to extracted text directory")
    passages_parser.add_argument(
        "--library-path",
        default="data/zotero-export/library.json",
        help="Path to library.json",
    )
    passages_parser.set_defaults(func=execute_search)

    passage_context_parser = search_subparsers.add_parser(
        "passage-context",
        help="Expand a passage handle into longer local context",
    )
    passage_context_parser.add_argument("--passage-handle", required=True, help="Passage handle returned by search_passages")
    passage_context_parser.add_argument(
        "--window",
        default="paragraph",
        choices=["match_only", "paragraph", "section", "page"],
        help="Context window to retrieve",
    )
    passage_context_parser.add_argument("--max-chars", type=int, default=2000, help="Maximum context characters")
    passage_context_parser.set_defaults(func=execute_search)

    wiki_section_parser = search_subparsers.add_parser(
        "wiki-section",
        help="Read the full content of a wiki handle or wiki section handle",
    )
    wiki_section_parser.add_argument("--wiki-handle", required=True, help="Wiki handle returned by search_wiki or ask_research")
    wiki_section_parser.add_argument(
        "--include-frontmatter",
        action="store_true",
        help="Include YAML frontmatter in the output",
    )
    wiki_section_parser.set_defaults(func=execute_search)

    ask_parser = search_subparsers.add_parser("ask", help="Ask a research question via wiki + PDF retrieval")
    ask_parser.add_argument("--query", required=True, help="Research question")
    ask_parser.add_argument(
        "--force-mode",
        default="auto",
        choices=["auto", "wiki", "pdf", "hybrid"],
        help="Force retrieval mode",
    )
    ask_parser.add_argument("--max-sources", type=int, default=5, help="Maximum source papers/snippets")
    ask_parser.add_argument("--db-path", default="data/vectordb", help="Path to ChromaDB persistent directory")
    _add_common_filter_args(ask_parser)
    ask_parser.set_defaults(func=execute_search)


def execute_search(args: argparse.Namespace) -> int:
    target = args.search_target
    output_json = bool(getattr(args, "json", False))
    filters = _parse_filters(args)

    if target == "wiki":
        params = {
            "query": args.query,
            "limit": args.limit,
            "db_path": args.db_path,
        }
        return _dispatch_and_render("search_wiki", params, output_json)

    if target == "library":
        params: dict[str, Any] = {
            "query": args.query,
            "limit": args.limit,
        }
        if filters:
            params["filters"] = filters
        return _dispatch_and_render("search_library", params, output_json)

    if target == "passages":
        params = {
            "query": args.query,
            "limit": args.limit,
            "search_mode": args.search_mode,
            "db_path": args.db_path,
            "text_dir": args.text_dir,
            "library_path": args.library_path,
        }
        if filters:
            params["filters"] = filters
        return _dispatch_and_render("search_passages", params, output_json)

    if target == "passage-context":
        params = {
            "passage_handle": args.passage_handle,
            "window": args.window,
            "max_chars": args.max_chars,
        }
        return _dispatch_and_render("get_passage_context", params, output_json)

    if target == "wiki-section":
        params = {
            "wiki_handle": args.wiki_handle,
            "include_frontmatter": args.include_frontmatter,
        }
        return _dispatch_and_render("get_wiki_page_section", params, output_json)

    if target == "ask":
        params = {
            "query": args.query,
            "force_mode": args.force_mode,
            "max_sources": args.max_sources,
            "db_path": args.db_path,
        }
        if filters:
            params["filters"] = filters
        return _dispatch_and_render("ask_research", params, output_json)

    print(f"Unknown search target: {target}")
    return 1
