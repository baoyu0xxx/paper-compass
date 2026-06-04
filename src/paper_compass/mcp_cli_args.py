"""Argument parsing and CLI-to-tool param routing for paper-compass MCP entrypoints."""

from __future__ import annotations

import argparse
from typing import Any

from paper_compass.env_utils import PROJECT_ROOT
from paper_compass.mcp_contracts import accepted_params, tool_names

DEFAULT_VECTORDB_PATH = str(PROJECT_ROOT / "data" / "vectordb")
DEFAULT_TEXT_DIR = str(PROJECT_ROOT / "data" / "texts")
DEFAULT_LIBRARY_PATH = str(PROJECT_ROOT / "data" / "zotero-export" / "library.json")
DEFAULT_WIKI_ROOT = "./wiki"


def parse_filters(args: argparse.Namespace) -> dict[str, Any] | None:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="paper-compass MCP server")
    parser.add_argument(
        "--tool",
        choices=tool_names(),
        help="Run a single tool call. Includes advanced tools such as search_wiki; MCP tools/list still exposes only public tools.",
    )
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--force-mode", default="auto", choices=["auto", "wiki", "pdf", "hybrid"])
    parser.add_argument(
        "--search-mode",
        default="semantic",
        choices=["semantic", "keyword", "hybrid"],
        help="Passage search mode for search_passages",
    )
    parser.add_argument("--max-sources", type=int, default=5, help="Maximum source papers/snippets for ask_research")
    parser.add_argument("--db-path", default=DEFAULT_VECTORDB_PATH, help="Path to ChromaDB persistent directory (local/internal)")
    parser.add_argument("--text-dir", default=DEFAULT_TEXT_DIR, help="Path to extracted text directory (local/internal)")
    parser.add_argument("--library-path", default=DEFAULT_LIBRARY_PATH, help="Path to library.json (local/internal)")
    parser.add_argument("--wiki-root", default=DEFAULT_WIKI_ROOT, help="Wiki root directory for save_to_wiki (local/internal)")
    parser.add_argument("--id-or-doi", help="Paper identifier (doc_id, DOI, or exact title)")
    parser.add_argument("--paper-handle", help="paper_handle returned by search_library")
    parser.add_argument("--passage-handle", help="passage_handle returned by search_passages")
    parser.add_argument("--wiki-handle", help="wiki_handle returned by ask_research or search_wiki")
    parser.add_argument("--window", default="paragraph", choices=["match_only", "paragraph", "section", "page"], help="Context window for get_passage_context")
    parser.add_argument("--max-chars", type=int, default=2000, help="Maximum characters for get_passage_context")
    parser.add_argument("--include-frontmatter", action="store_true", help="Include YAML frontmatter when reading a wiki page/section")
    parser.add_argument("--title", help="Wiki page title (for save_to_wiki)")
    parser.add_argument("--content", help="Wiki page content (for save_to_wiki)")
    parser.add_argument("--type", dest="page_type", default="queries", choices=["queries", "topics", "methods", "comparisons"], help="save_to_wiki target type")
    parser.add_argument("--confidence", default="medium", choices=["high", "medium", "low"])
    parser.add_argument("--tag", action="append", default=[], help="Tags (repeatable)")
    parser.add_argument("--source", action="append", default=[], help="Source refs (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="Preview save_to_wiki output without writing. This is the default behavior.")
    parser.add_argument("--commit", action="store_true", help="Actually write save_to_wiki output to disk (overrides preview default)")
    parser.add_argument("--upsert-mode", default="create", choices=["create", "replace_if_same_slug", "merge"], help="Upsert strategy for save_to_wiki commits")
    parser.add_argument("--filter-collections", action="append", help="Filter by collection")
    parser.add_argument("--filter-tags", action="append", help="Filter by tag")
    parser.add_argument("--filter-authors", action="append", help="Filter by author")
    parser.add_argument("--filter-year-from", type=int, help="Filter by minimum year")
    parser.add_argument("--filter-year-to", type=int, help="Filter by maximum year")
    parser.add_argument("--interactive", action="store_true", help="Interactive tool shell with public/advanced tool hints")
    parser.add_argument("--mcp", action="store_true", help="Run MCP JSON-RPC server over stdio")
    return parser


def build_tool_params(tool_name: str, args: argparse.Namespace) -> dict[str, Any]:
    allowed_params = set(accepted_params(tool_name))
    params: dict[str, Any] = {}

    mapping = {
        "query": getattr(args, "query", None),
        "limit": getattr(args, "limit", None),
        "force_mode": getattr(args, "force_mode", None),
        "search_mode": getattr(args, "search_mode", None),
        "max_sources": getattr(args, "max_sources", None),
        "db_path": getattr(args, "db_path", None),
        "text_dir": getattr(args, "text_dir", None),
        "library_path": getattr(args, "library_path", None),
        "wiki_root": getattr(args, "wiki_root", None),
        "id_or_doi": getattr(args, "id_or_doi", None),
        "paper_handle": getattr(args, "paper_handle", None),
        "passage_handle": getattr(args, "passage_handle", None),
        "wiki_handle": getattr(args, "wiki_handle", None),
        "window": getattr(args, "window", None),
        "max_chars": getattr(args, "max_chars", None),
        "include_frontmatter": getattr(args, "include_frontmatter", None),
        "title": getattr(args, "title", None),
        "content": getattr(args, "content", None),
        "target_type": getattr(args, "page_type", None),
        "confidence": getattr(args, "confidence", None),
        "tags": getattr(args, "tag", None),
        "source_refs": getattr(args, "source", None),
        "upsert_mode": getattr(args, "upsert_mode", None),
    }

    for param_name, value in mapping.items():
        if param_name not in allowed_params:
            continue
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        params[param_name] = value

    filters = parse_filters(args)
    if filters and "filters" in allowed_params:
        params["filters"] = filters

    if tool_name == "save_to_wiki" and "dry_run" in allowed_params:
        commit = bool(getattr(args, "commit", False))
        dry_run_flag = bool(getattr(args, "dry_run", False))
        params["commit"] = commit
        params["dry_run"] = False if commit else (True if dry_run_flag else True)

    return params
