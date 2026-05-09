"""paper-compass CLI — model selection and configuration.

Usage:
    paper-compass init       Configure LLM and embedding providers
    paper-compass validate   Test connectivity and configuration

See `paper-compass <command> --help` for details.
"""

from __future__ import annotations

import argparse
import sys

from paper_compass.cli import configure, validate


def main() -> int:
    """Main CLI entry point (registered in pyproject.toml)."""
    parser = argparse.ArgumentParser(
        prog="paper-compass",
        description="Personal academic paper retrieval and knowledge navigation",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        metavar="COMMAND",
    )

    configure.add_subcommand_parser(subparsers)
    validate.add_subcommand_parser(subparsers)

    if len(sys.argv) < 2:
        parser.print_help()
        return 0

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
