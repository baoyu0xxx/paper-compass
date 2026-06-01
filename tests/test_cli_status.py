"""Tests for paper-compass status CLI."""

from __future__ import annotations

import pytest

from paper_compass.cli import main


@pytest.fixture
def fake_status_payload():
    return {
        "project_root": "/repo",
        "package_project_root": "/repo",
        "env_path": "/repo/.env",
        "env_loaded": True,
        "llm": {
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
            "api_key": "sk-...abcd (20 chars)",
        },
        "embedding": {
            "role": "embedding",
            "config_source": "shared",
            "selected_provider": "embedding_volcengine",
            "resolved_provider": "embedding_volcengine",
            "local_fallback_model": "bge-base",
            "display_cascade": [
                "embedding_volcengine",
                "embedding_main",
                "local (bge-base)",
            ],
            "legacy_fields": [],
            "configured_candidates": [
                {
                    "name": "embedding_volcengine",
                    "provider": "volcengine",
                    "base_url": "https://ark.example.com",
                    "model": "ep-123",
                    "api_key": "ark-...efgh (18 chars)",
                    "api_key_configured": True,
                },
                {
                    "name": "embedding_main",
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model": "text-embedding-3-small",
                    "api_key": "sk-...wxyz (24 chars)",
                    "api_key_configured": True,
                },
            ],
        },
        "wiki_prompt": {
            "selection": "default",
            "prompt_dir": "prompts",
            "mode": "normal",
            "fallback_enabled": True,
            "router_loaded": True,
            "overview_loaded": True,
            "empirical_loaded": True,
            "fallback_loaded": True,
            "reason": "",
        },
        "library": {
            "path": "/repo/data/zotero-export/library.json",
            "record_count": 12,
        },
        "wiki": {
            "root": "/repo/wiki",
            "page_counts": {"papers": 8, "topics": 3},
        },
        "vectordb": {
            "path": "/repo/data/vectordb",
            "health": {
                "severity": "ok",
                "summary": "vectordb health looks normal",
                "recommended_action": "No action needed.",
            },
            "collections": [
                {
                    "name": "papers_openai_text-embedding-3-small",
                    "count": 120,
                    "embedding_model": "openai:text-embedding-3-small",
                }
            ],
        },
    }


def test_status_cli_json(monkeypatch, capsys, fake_status_payload):
    monkeypatch.setattr("paper_compass.cli.status.collect_status", lambda: fake_status_payload)
    monkeypatch.setattr("sys.argv", ["paper-compass", "status", "--json"])

    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert '"project_root": "/repo"' in out
    assert '"record_count": 12' in out
    assert '"severity": "ok"' in out


def test_status_cli_text(monkeypatch, capsys, fake_status_payload):
    monkeypatch.setattr("paper_compass.cli.status.collect_status", lambda: fake_status_payload)
    monkeypatch.setattr("sys.argv", ["paper-compass", "status"])

    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "paper-compass status" in out
    assert "project root: /repo" in out
    assert "records: 12" in out
    assert "health: ok" in out
    assert "embedding role: embedding | source=shared | selected=embedding_volcengine | active=embedding_volcengine" in out
    assert "prompt bundle: normal | selection=default | dir=prompts" in out
    assert "papers_openai_text-embedding-3-small" in out
