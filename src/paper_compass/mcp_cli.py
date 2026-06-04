"""Legacy import shim for stale paper-compass-mcp wrappers.

The canonical console-script target is now ``paper_compass.mcp_entrypoint:main``.
This module remains importable so already-generated wrappers that still point at
``paper_compass.mcp_cli:main`` continue to work until their environment is
refreshed.
"""

from __future__ import annotations

from paper_compass.mcp_entrypoint import main


if __name__ == "__main__":
    raise SystemExit(main())
