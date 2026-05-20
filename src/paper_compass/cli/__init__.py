"""paper-compass CLI — model selection, search, status, data sync, and configuration.

Usage:
    paper-compass init       Configure LLM and embedding providers
    paper-compass search     Search wiki, library, passages, or ask_research
    paper-compass status     Show resolved config and local index status
    paper-compass sync       Run incremental data sync for Zotero / index / wiki
    paper-compass update     Update to the latest version
    paper-compass validate   Test connectivity and configuration

See `paper-compass <command> --help` for details.
"""

from __future__ import annotations

import argparse
import sys

from paper_compass import __version__
from paper_compass.cli import configure, search, status, sync_data, update, validate


def main() -> int:
    """Main CLI entry point (registered in pyproject.toml)."""
    parser = argparse.ArgumentParser(
        prog="paper-compass",
        description="Personal academic paper retrieval and knowledge navigation",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
    )
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        metavar="COMMAND",
    )

    configure.add_subcommand_parser(subparsers)
    search.add_subcommand_parser(subparsers)
    status.add_subcommand_parser(subparsers)
    sync_data.add_subcommand_parser(subparsers)
    update.add_subcommand_parser(subparsers)
    validate.add_subcommand_parser(subparsers)

    if len(sys.argv) < 2:
        parser.print_help()
        return 0

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
