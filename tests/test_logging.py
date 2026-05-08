"""Tests for JSONL trace logging."""

import json
from pathlib import Path

from miniresearch.logging import emit_trace


def test_emit_trace_writes_when_enabled(tmp_path, monkeypatch):
    trace_path = tmp_path / "traces.jsonl"

    def _fake_load_all_configs(config_dir="configs"):
        return {
            "mcp": {
                "mcp": {
                    "trace": {
                        "enabled": True,
                        "path": str(trace_path),
                        "include_query_text": True,
                        "include_source_ids": True,
                    }
                }
            }
        }

    monkeypatch.setattr("miniresearch.logging.load_all_configs", _fake_load_all_configs)

    emit_trace({"tool": "search_library", "ok": True, "query": "family firm", "source_ids": ["A"]})

    assert trace_path.exists()
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["tool"] == "search_library"
    assert payload["query"] == "family firm"


def test_emit_trace_respects_exclusion_flags(tmp_path, monkeypatch):
    trace_path = tmp_path / "traces2.jsonl"

    def _fake_load_all_configs(config_dir="configs"):
        return {
            "mcp": {
                "mcp": {
                    "trace": {
                        "enabled": True,
                        "path": str(trace_path),
                        "include_query_text": False,
                        "include_source_ids": False,
                    }
                }
            }
        }

    monkeypatch.setattr("miniresearch.logging.load_all_configs", _fake_load_all_configs)

    emit_trace({"tool": "ask_research", "ok": True, "query": "q", "source_ids": ["X"]})

    payload = json.loads(trace_path.read_text(encoding="utf-8").strip())
    assert "query" not in payload
    assert "source_ids" not in payload
