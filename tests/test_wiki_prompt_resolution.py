"""Tests for wiki prompt resolution in paper-compass.

Tests WikiGenerator prompt resolution and CLI --wiki-prompt flag.
"""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from paper_compass.cli.configure import (
    _available_disciplines,
    _write_dotenv,
)


# ── Prompt directory resolution tests ────────────────────────────────────


class TestResolvePromptDir:
    """Test _resolve_prompt_dir() via WikiGenerator."""

    def test_default_when_unset(self, monkeypatch):
        """WIKI_PROMPT unset → 'prompts' directory."""
        monkeypatch.delenv("WIKI_PROMPT", raising=False)
        from paper_compass.wiki_gen import WikiGenerator

        gen = WikiGenerator()
        assert gen._resolve_prompt_dir() == "prompts"

    def test_default_when_default(self, monkeypatch):
        """WIKI_PROMPT='default' → 'prompts' directory."""
        monkeypatch.setenv("WIKI_PROMPT", "default")
        from paper_compass.wiki_gen import WikiGenerator

        gen = WikiGenerator()
        assert gen._resolve_prompt_dir() == "prompts"

    def test_economics_discipline(self, monkeypatch):
        """WIKI_PROMPT='economics' → 'prompts/disciplines/economics'."""
        monkeypatch.setenv("WIKI_PROMPT", "economics")
        from paper_compass.wiki_gen import WikiGenerator

        gen = WikiGenerator()
        assert gen._resolve_prompt_dir() == "prompts/disciplines/economics"

    def test_custom_path(self, monkeypatch):
        """WIKI_PROMPT='my/custom/prompts' → as-is."""
        monkeypatch.setenv("WIKI_PROMPT", "my/custom/prompts")
        from paper_compass.wiki_gen import WikiGenerator

        gen = WikiGenerator()
        assert gen._resolve_prompt_dir() == "my/custom/prompts"

    def test_absolute_custom_path(self, monkeypatch):
        """WIKI_PROMPT='/absolute/path' → as-is."""
        monkeypatch.setenv("WIKI_PROMPT", "/absolute/path/to/prompts")
        from paper_compass.wiki_gen import WikiGenerator

        gen = WikiGenerator()
        assert gen._resolve_prompt_dir() == "/absolute/path/to/prompts"

    def test_unknown_discipline_treated_as_custom_path(self, monkeypatch):
        """WIKI_PROMPT='physics' (no such discipline) → custom path."""
        monkeypatch.setenv("WIKI_PROMPT", "physics")
        from paper_compass.wiki_gen import WikiGenerator

        gen = WikiGenerator()
        # Falls through to custom path
        assert gen._resolve_prompt_dir() == "physics"


class TestAvailableDisciplines:
    """Test _available_disciplines() discovery."""

    def test_includes_economics(self):
        """Economics preset must be discoverable."""
        disciplines = _available_disciplines()
        assert "economics" in disciplines, (
            f"Expected 'economics' in disciplines, got: {disciplines}"
        )

    def test_returns_list(self):
        """Must return a list."""
        assert isinstance(_available_disciplines(), list)

    def test_missing_directory_returns_empty(self, monkeypatch):
        """If prompts/disciplines/ doesn't exist, return []."""
        # Patch Path.exists to simulate missing dir
        from paper_compass.wiki_gen import WikiGenerator

        with mock.patch.object(Path, "exists", return_value=False):
            # The _available_disciplines in configure.py is independent
            # We test via the staticmethod on WikiGenerator
            disc = WikiGenerator._available_disciplines()
            assert disc == []


# ── CLI integration tests ────────────────────────────────────────────────


class TestWriteDotenvWithWikiPrompt:
    """Test that _write_dotenv writes WIKI_PROMPT correctly."""

    def test_writes_wiki_prompt(self):
        """WIKI_PROMPT should appear in .env output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")
            _write_dotenv(
                env_path,
                llm_config={"LLM_BASE_URL": "https://api.example.com", "LLM_API_KEY": "sk-test"},
                embed_config={"EMBED_BASE_URL": "https://api.example.com", "EMBED_API_KEY": "sk-test"},
                wiki_prompt="economics",
                force=True,
            )
            content = Path(env_path).read_text(encoding="utf-8")
            assert "WIKI_PROMPT=economics" in content

    def test_writes_default_wiki_prompt(self):
        """WIKI_PROMPT=default should appear in .env."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")
            _write_dotenv(
                env_path,
                llm_config={"LLM_BASE_URL": "https://api.example.com", "LLM_API_KEY": "sk-test"},
                embed_config={"EMBED_BASE_URL": "https://api.example.com", "EMBED_API_KEY": "sk-test"},
                wiki_prompt="default",
                force=True,
            )
            content = Path(env_path).read_text(encoding="utf-8")
            assert "WIKI_PROMPT=default" in content

    def test_writes_custom_wiki_prompt(self):
        """WIKI_PROMPT with custom path should appear in .env."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")
            _write_dotenv(
                env_path,
                llm_config={"LLM_BASE_URL": "https://api.example.com", "LLM_API_KEY": "sk-test"},
                embed_config={"EMBED_BASE_URL": "https://api.example.com", "EMBED_API_KEY": "sk-test"},
                wiki_prompt="/home/user/my-prompts",
                force=True,
            )
            content = Path(env_path).read_text(encoding="utf-8")
            assert "WIKI_PROMPT=/home/user/my-prompts" in content

    def test_no_wiki_prompt_when_empty(self):
        """Empty wiki_prompt should not write WIKI_PROMPT line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")
            _write_dotenv(
                env_path,
                llm_config={"LLM_BASE_URL": "https://api.example.com", "LLM_API_KEY": "sk-test"},
                embed_config={"EMBED_BASE_URL": "https://api.example.com", "EMBED_API_KEY": "sk-test"},
                wiki_prompt="",
                force=True,
            )
            content = Path(env_path).read_text(encoding="utf-8")
            assert "WIKI_PROMPT" not in content


# ── WikiGenerator smoke tests ────────────────────────────────────────────


class TestWikiGeneratorWithPromptDirs:
    """Verify WikiGenerator loads prompts from correct directories."""

    def test_default_prompts_load(self, monkeypatch):
        """Default prompt set should load successfully."""
        monkeypatch.setenv("WIKI_PROMPT", "default")
        from paper_compass.wiki_gen import WikiGenerator

        gen = WikiGenerator()
        assert gen._router_prompt, "router prompt should be loaded"
        assert gen._overview_prompt, "default overview prompt should be loaded"
        assert gen._empirical_prompt, "default empirical prompt should be loaded"
        assert gen._fallback_prompt, "fallback prompt should be loaded"

    def test_economics_prompts_load(self, monkeypatch):
        """Economics preset should load successfully."""
        monkeypatch.setenv("WIKI_PROMPT", "economics")
        from paper_compass.wiki_gen import WikiGenerator

        gen = WikiGenerator()
        assert gen._router_prompt, "router prompt should be loaded"
        assert gen._overview_prompt, "economics overview prompt should be loaded"
        assert gen._empirical_prompt, "economics empirical prompt should be loaded"
        assert gen._fallback_prompt, "fallback prompt should be loaded"

    def test_fallback_prompt_always_loads(self, monkeypatch):
        """Fallback prompt loads from prompts/wiki_ingest.md regardless of WIKI_PROMPT."""
        monkeypatch.setenv("WIKI_PROMPT", "economics")
        from paper_compass.wiki_gen import WikiGenerator

        gen = WikiGenerator()
        assert gen._fallback_prompt, "fallback prompt must always load"
        assert "research wiki" in gen._fallback_prompt.lower()
