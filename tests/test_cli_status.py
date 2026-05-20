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
            "main": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "text-embedding-3-small",
                "api_key": "sk-...wxyz (24 chars)",
            },
            "volcengine": {
                "provider": "volcengine",
                "base_url": "https://ark.example.com",
                "model": "ep-123",
                "api_key": "ark-...efgh (18 chars)",
            },
            "local_fallback_model": "bge-base",
            "cascade_order": [
                "embedding_main (openai:text-embedding-3-small)",
                "embedding_volcengine (volcengine:ep-123)",
                "local (bge-base)",
            ],
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
    assert "papers_openai_text-embedding-3-small" in out
