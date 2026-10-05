"""Service adapter for MCP-triggered paper index maintenance.

The indexing algorithm remains owned by ``scripts/build_index.py`` for CLI
compatibility; this module supplies a typed, stable MCP boundary.
"""

from __future__ import annotations

import importlib.util
from argparse import Namespace
from pathlib import Path
from typing import Any

from paper_compass.env_utils import PROJECT_ROOT


_BUILD_INDEX_PATH = PROJECT_ROOT / "scripts" / "build_index.py"


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("paper_compass_build_index_service", _BUILD_INDEX_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load index builder: {_BUILD_INDEX_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def index_incremental(
    *,
    library_path: str,
    db_path: str,
    text_dir: str,
    manifest_path: str = "",
    dry_run: bool = True,
    prune_deleted: bool = False,
    allow_large_incremental: bool = False,
    explain_changes: bool = False,
    sample_size: int = 5,
) -> dict[str, Any]:
    """Run the existing paper incremental planner through a service API."""
    if not library_path:
        raise ValueError("library_path is required")
    args = Namespace(
        library=library_path,
        db_path=db_path,
        text_dir=text_dir,
        extract_text=False,
        wiki=False,
        wiki_root=str(PROJECT_ROOT / "wiki"),
        incremental=True,
        full_rebuild=False,
        prune_deleted=prune_deleted,
        manifest_path=manifest_path,
        dry_run=dry_run,
        allow_large_incremental=allow_large_incremental,
        explain_changes=explain_changes,
        sample_size=max(0, int(sample_size)),
    )
    return _load_builder().index_papers(args)
