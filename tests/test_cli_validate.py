"""Tests for paper-compass validate subcommand."""

from __future__ import annotations

from pathlib import Path

from paper_compass.cli.validate import _check_dotenv


def test_check_dotenv_rejects_unresolved_env_refs(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "LLM_BASE_URL=https://api.example.com/v1",
                "LLM_API_KEY=$OPENAI_API_KEY",
                "EMBED_BASE_URL=https://embed.example.com/v1",
                "EMBED_API_KEY=$EMBED_KEY",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EMBED_KEY", raising=False)

    name, status = _check_dotenv(str(env_path))

    assert name == "dotenv"
    assert status.startswith("ERROR:")
    assert "OPENAI_API_KEY" in status
    assert "EMBED_KEY" in status


def test_check_dotenv_accepts_resolved_env_refs(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "LLM_BASE_URL=https://api.example.com/v1",
                "LLM_API_KEY=$OPENAI_API_KEY",
                "EMBED_BASE_URL=https://embed.example.com/v1",
                "EMBED_API_KEY=$EMBED_KEY",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
    monkeypatch.setenv("EMBED_KEY", "embed-real")

    name, status = _check_dotenv(str(env_path))

    assert name == "dotenv"
    assert status == "OK"
