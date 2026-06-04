#!/usr/bin/env python3
"""Repo-local compatibility shim for the shared paper-compass MCP entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paper_compass.mcp_entrypoint import main


if __name__ == "__main__":
    sys.exit(main())
