"""Compatibility wrapper for legacy `scripts.run_mcp_server` entrypoints."""

from __future__ import annotations

from paper_compass.mcp_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
