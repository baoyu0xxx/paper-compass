"""Lightweight JSONL trace logging for MCP tool calls."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from paper_compass.config import load_all_configs


DEFAULT_TRACE_CONFIG = {
    "enabled": False,
    "path": "data/traces/mcp_traces.jsonl",
    "include_query_text": True,
    "include_source_ids": True,
}


def get_trace_config() -> Dict[str, Any]:
    configs = load_all_configs()
    mcp_cfg = configs.get("mcp", {}).get("mcp", {})
    trace_cfg = mcp_cfg.get("trace", {})
    merged = dict(DEFAULT_TRACE_CONFIG)
    merged.update(trace_cfg)
    return merged


def emit_trace(event: Dict[str, Any]) -> None:
    cfg = get_trace_config()
    if not cfg.get("enabled", False):
        return

    path = Path(cfg.get("path") or DEFAULT_TRACE_CONFIG["path"])
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = dict(event)
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

    if not cfg.get("include_query_text", True):
        payload.pop("query", None)
    if not cfg.get("include_source_ids", True):
        payload.pop("source_ids", None)

    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # Fail-safe: tracing should never break tool execution
        return
