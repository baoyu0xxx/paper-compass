"""Tests for MCP handler parameter handling."""

from __future__ import annotations

from paper_compass.mcp_server import handle_tool


def test_handle_tool_reports_unsupported_parameters():
    result = handle_tool("search_library", {"query": "test", "bogus": 1})

    assert result["ok"] is True
    assert any("Unsupported" in warning or "unsupported" in warning for warning in result["warnings"])
