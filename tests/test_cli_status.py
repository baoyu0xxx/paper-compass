"""Tests for paper-compass status CLI."""

from __future__ import annotations

import json

import pytest

from paper_compass.cli import main


@pytest.fixture
def fake_status_payload():
    return {
        "project_root": "/repo",
        "package_project_root": "/repo",
        "env_path": "/repo/.env",
        "env_loaded": True,
        "runtime": {
            "status": "active",
            "managed_venv": "/repo/.venv",
            "managed_python": "/repo/.venv/bin/python",
            "current_python": "/repo/.venv/bin/python",
            "python_version": "3.12.7",
            "reasons": [],
        },
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
        "sync": {
            "last_sync": {
                "status": "ok",
                "stage": "completed",
                "started_at": "2026-06-23T01:47:27Z",
                "updated_at": "2026-06-23T01:48:59Z",
                "finished_at": "2026-06-23T01:49:00Z",
                "run_id": "20260623-014727-1234",
            },
            "lock": {
                "exists": True,
                "stale": True,
                "reason": "pid not running",
                "path": "/repo/data/state/sync.lock",
            },
            "last_successful_zotero_source": {
                "db_path": "D:/zotero_backup/zotero.sqlite",
                "storage_path": "D:/zotero_backup/storage",
                "source_kind": "explicit",
                "is_live_candidate": False,
            },
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
    assert '"managed_python": "/repo/.venv/bin/python"' in out
    assert '"last_successful_zotero_source"' in out
    assert '"stale": true' in out
    assert '"updated_at": "2026-06-23T01:48:59Z"' in out


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
    assert "runtime" in out.lower()
    assert "managed python: /repo/.venv/bin/python" in out
    assert "status: active" in out
    assert "embedding role: embedding | source=shared | selected=embedding_volcengine | active=embedding_volcengine" in out
    assert "prompt bundle: normal | selection=default | dir=prompts" in out
    assert "papers_openai_text-embedding-3-small" in out
    assert "last status: ok" in out
    assert "updated at: 2026-06-23T01:48:59Z" in out
    assert "lock: stale=yes" in out
    assert "zotero source: D:/zotero_backup/zotero.sqlite" in out
