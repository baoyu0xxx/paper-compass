"""Tests for paper-compass validate CLI output."""

from __future__ import annotations

import argparse

from paper_compass.cli.validate import execute_validate


def test_validate_prints_config_summary(monkeypatch, capsys):
    monkeypatch.setattr("paper_compass.cli.validate.load_project_env", lambda env_path=None: True)
    monkeypatch.setattr(
        "paper_compass.cli.validate.load_all_configs",
        lambda: {
            "providers": {
                "providers": {
                    "embedding_main": {},
                    "embedding_volcengine": {},
                },
                "roles": {
                    "embedding": "embedding_volcengine",
                },
            }
        },
    )

    monkeypatch.setattr(
        "paper_compass.cli.validate.resolve_embedding_runtime",
        lambda _configs: {
            "role": "embedding",
            "config_source": "shared",
            "selected_provider": "embedding_volcengine",
            "resolved_provider": "embedding_volcengine",
            "resolved_cloud_config": {
                "provider": "volcengine",
                "base_url": "https://ark.example.com",
                "model": "ep-123",
            },
            "candidate_order": ["embedding_volcengine", "embedding_main"],
            "display_cascade": [
                "embedding_volcengine",
                "embedding_main",
                "local (bge-base)",
            ],
            "local_fallback_model": "bge-base",
            "legacy_fields": [],
            "configured_candidates": [
                {
                    "name": "embedding_volcengine",
                    "provider": "volcengine",
                    "base_url": "https://ark.example.com",
                    "model": "ep-123",
                    "api_key_configured": True,
                },
                {
                    "name": "embedding_main",
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model": "text-embedding-3-small",
                    "api_key_configured": True,
                },
            ],
        },
    )

    def fake_provider(name, configs):
        mapping = {
            "wiki_generation": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o",
            },
            "embedding_main": {
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "model": "text-embedding-3-small",
            },
            "embedding_volcengine": {
                "provider": "volcengine",
                "base_url": "https://ark.example.com",
                "model": "ep-123",
            },
        }
        return mapping[name]

    monkeypatch.setattr("paper_compass.cli.validate.get_provider_config", fake_provider)
    monkeypatch.setattr("paper_compass.cli.validate._check_dotenv", lambda env_path: ("dotenv", "OK"))
    monkeypatch.setattr("paper_compass.cli.validate._test_llm", lambda: ("llm", "OK (model: gpt-4o, 0.1s, response: 4 chars)"))
    monkeypatch.setattr("paper_compass.cli.validate._test_embedding", lambda: ("embed", "OK (model: ep-123, dim=2048, 0.1s)"))
    monkeypatch.setenv("LOCAL_EMBED_MODEL", "bge-base")

    rc = execute_validate(argparse.Namespace(env_path="/tmp/fake.env"))
    assert rc == 0

    out = capsys.readouterr().out
    assert "config: project_root=" in out
    assert "config: env_path=/tmp/fake.env" in out
    assert "config: llm=openai | https://api.openai.com/v1 | gpt-4o" in out
    assert "config: embedding_role=embedding | source=shared | selected=embedding_volcengine | active=embedding_volcengine" in out
    assert "config: embedding_candidates=embedding_volcengine -> embedding_main -> local (bge-base)" in out
    assert "config: embedding_registry=embedding_volcengine[volcengine|https://ark.example.com|ep-123] ; embedding_main[openai|https://api.openai.com/v1|text-embedding-3-small]" in out
