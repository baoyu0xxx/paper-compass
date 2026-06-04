"""Interactive helper shell for local MCP tool probing."""

from __future__ import annotations

import json
from typing import Any, Callable

from paper_compass.mcp_contracts import list_tools


ToolHandler = Callable[[str, dict[str, Any]], dict[str, Any]]


def public_tool_names() -> list[str]:
    return [tool["name"] for tool in list_tools()]


def advanced_tool_names() -> list[str]:
    return [tool["name"] for tool in list_tools(visibility="all") if tool.get("visibility") == "advanced"]


def interactive_banner() -> str:
    public = ", ".join(public_tool_names())
    advanced = ", ".join(advanced_tool_names()) or "(none)"
    return (
        "paper-compass MCP — interactive mode\n"
        f"Public tools: {public}\n"
        f"Advanced tools: {advanced}\n"
        "Type 'help' for usage, 'quit' to exit.\n"
    )


def interactive_mode(handle_tool: ToolHandler) -> None:
    print(interactive_banner())

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
            print("  search_library <query>")
            print("  search_passages <query>")
            print("  ask_research <query>")
            print("  get_paper_metadata <paper_handle_or_id_or_doi>")
            print("  get_passage_context <passage_handle>")
            print("  get_wiki_page_section <wiki_handle>")
            print("  save_to_wiki <title> | <content>")
            print("  search_wiki <query>  # advanced")
            continue

        parts = line.split(maxsplit=1)
        tool_name = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        params: dict[str, Any] = {}
        if tool_name == "search_wiki":
            params = {"query": rest, "limit": 5}
        elif tool_name == "search_library":
            params = {"query": rest, "limit": 10}
        elif tool_name == "search_passages":
            params = {"query": rest, "limit": 10}
        elif tool_name == "ask_research":
            params = {"query": rest, "force_mode": "auto"}
        elif tool_name == "get_paper_metadata":
            if rest.startswith("paper:"):
                params = {"paper_handle": rest}
            else:
                params = {"id_or_doi": rest}
        elif tool_name == "get_passage_context":
            params = {"passage_handle": rest}
        elif tool_name == "get_wiki_page_section":
            params = {"wiki_handle": rest}
        elif tool_name == "save_to_wiki":
            if "|" not in rest:
                print("  Usage: save_to_wiki <title> | <content>")
                continue
            title_part, content_part = rest.split("|", 1)
            params = {"title": title_part.strip(), "content": content_part.strip(), "dry_run": True}
        else:
            print(f"  Unknown tool: {tool_name}")
            continue

        result = handle_tool(tool_name, params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()
