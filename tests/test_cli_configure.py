"""Tests for paper-compass CLI configure module (.env generation).

Tests the interactive and non-interactive configuration modes.
"""

import os
import tempfile
from pathlib import Path

import pytest

from paper_compass.cli.configure import (
    _embed_args_to_env,
    _llm_args_to_env,
    _write_dotenv,
)


class TestLlmArgsToEnv:
    def test_full_config(self):
        result = _llm_args_to_env({
            "base_url": "https://api.openai.com/v1",
            "api_key": "$OPENAI_API_KEY",
            "model": "gpt-4o",
        })
        assert result == {
            "LLM_BASE_URL": "https://api.openai.com/v1",
            "LLM_API_KEY": "$OPENAI_API_KEY",
            "LLM_MODEL": "gpt-4o",
        }

    def test_partial_config(self):
        result = _llm_args_to_env({"base_url": "https://example.com"})
        assert result == {"LLM_BASE_URL": "https://example.com"}
        assert "LLM_API_KEY" not in result
        assert "LLM_MODEL" not in result

    def test_empty(self):
        assert _llm_args_to_env({}) == {}


class TestEmbedArgsToEnv:
    def test_openai_full(self):
        result = _embed_args_to_env({
            "api_style": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "$OPENAI_API_KEY",
            "model": "text-embedding-3-small",
        })
        assert result == {
            "EMBED_BASE_URL": "https://api.openai.com/v1",
            "EMBED_API_KEY": "$OPENAI_API_KEY",
            "EMBED_MODEL": "text-embedding-3-small",
        }

    def test_volcengine_full(self):
        result = _embed_args_to_env({
            "api_style": "volcengine",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal",
            "api_key": "$VOLC_API_KEY",
            "model": "doubao-embedding-vision-250615",
        })
        assert result == {
            "VOLC_EMBED_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal",
            "VOLC_EMBED_API_KEY": "$VOLC_API_KEY",
            "VOLC_EMBED_MODEL": "doubao-embedding-vision-250615",
        }

    def test_default_style_is_openai(self):
        result = _embed_args_to_env({
            "base_url": "https://example.com",
            "api_key": "sk-123",
        })
        assert "EMBED_BASE_URL" in result
        assert "VOLC_EMBED_BASE_URL" not in result

    def test_empty(self):
        assert _embed_args_to_env({}) == {}


class TestWriteDotenv:
    @pytest.fixture
    def tmp_env(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False, encoding="utf-8"
        ) as f:
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()

    def test_fresh_write(self, tmp_env):
        """Should write a complete .env from scratch when force=True."""
        llm = {"LLM_BASE_URL": "https://example.com", "LLM_API_KEY": "$MY_KEY", "LLM_MODEL": "gpt-4"}
        embed = {"EMBED_BASE_URL": "https://embed.example.com", "EMBED_API_KEY": "$MY_EMBED_KEY", "EMBED_MODEL": "text-embedding-3"}

        _write_dotenv(str(tmp_env), llm, embed, force=True)

        content = tmp_env.read_text(encoding="utf-8")
        assert "LLM_BASE_URL=https://example.com" in content
        assert "LLM_API_KEY=$MY_KEY" in content
        assert "LLM_MODEL=gpt-4" in content
        assert "EMBED_BASE_URL=https://embed.example.com" in content
        assert "EMBED_API_KEY=$MY_EMBED_KEY" in content

    def test_volcengine_write(self, tmp_env):
        """Volcengine embed vars written correctly."""
        llm = {"LLM_BASE_URL": "https://example.com", "LLM_API_KEY": "sk-123"}
        embed = {
            "VOLC_EMBED_BASE_URL": "https://volc.example.com",
            "VOLC_EMBED_API_KEY": "$VOLC_KEY",
            "VOLC_EMBED_MODEL": "ep-123",
        }

        _write_dotenv(str(tmp_env), llm, embed, force=True)

        content = tmp_env.read_text(encoding="utf-8")
        assert "VOLC_EMBED_BASE_URL=https://volc.example.com" in content
        assert "VOLC_EMBED_API_KEY=$VOLC_KEY" in content
        assert "VOLC_EMBED_MODEL=ep-123" in content
        # OpenAI embed vars should NOT appear (only VOLC_EMBED_* variants)
        lines = content.split("\n")
        assert not any(line.startswith("EMBED_BASE_URL=") for line in lines)
        assert not any(line.startswith("EMBED_API_KEY=") for line in lines)
        assert not any(line.startswith("EMBED_MODEL=") for line in lines)

    def test_merge_to_existing(self, tmp_env):
        """Should merge new keys into existing .env without overwriting unrelated keys."""
        # Create a .env with existing vars
        tmp_env.write_text(
            "EXISTING_VAR=hello\nLLM_BASE_URL=https://old.example.com\n",
            encoding="utf-8",
        )

        llm = {"LLM_BASE_URL": "https://new.example.com", "LLM_API_KEY": "sk-new"}
        embed = {"EMBED_BASE_URL": "https://embed.example.com", "EMBED_API_KEY": "sk-embed"}

        _write_dotenv(str(tmp_env), llm, embed, force=False)

        content = tmp_env.read_text(encoding="utf-8")
        # Existing non-conflicting var preserved
        assert "EXISTING_VAR=hello" in content
        # LLM_BASE_URL updated
        assert "LLM_BASE_URL=https://new.example.com" in content
        # Old value NOT present
        assert "https://old.example.com" not in content
        # New keys appended
        assert "EMBED_BASE_URL=https://embed.example.com" in content
        assert "EMBED_API_KEY=sk-embed" in content
