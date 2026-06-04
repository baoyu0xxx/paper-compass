"""Shared MCP CLI / stdio entrypoint logic for paper-compass."""

from __future__ import annotations

import json
import sys

from paper_compass import __version__
from paper_compass.mcp_cli_args import build_parser, build_tool_params
from paper_compass.mcp_interactive import interactive_mode
from paper_compass.mcp_server import handle_tool
from paper_compass.mcp_stdio import mcp_stdio_mode
from paper_compass.runtime_env import ManagedRuntimeError, assert_managed_runtime_active


def main(argv: list[str] | None = None) -> int:
    try:
        assert_managed_runtime_active(context="MCP server")
    except (ManagedRuntimeError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 1

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mcp:
        mcp_stdio_mode(handle_tool, version=__version__)
        return 0

    if args.interactive:
        interactive_mode(handle_tool)
        return 0

    if not args.tool:
        parser.print_help()
        return 0

    result = handle_tool(args.tool, build_tool_params(args.tool, args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
