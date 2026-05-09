"""Tests for config loader module."""

import os
import tempfile
from pathlib import Path

import pytest

from paper_compass.config import (
    load_yaml_config,
    load_all_configs,
    get_provider_config,
)


class TestLoadYamlConfig:
    def test_load_valid_yaml(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("version: 1\npaths:\n  wiki_root: ./wiki\n")
            tmp_path = f.name

        try:
            cfg = load_yaml_config(tmp_path)
            assert cfg["version"] == 1
            assert cfg["paths"]["wiki_root"] == "./wiki"
        finally:
            Path(tmp_path).unlink()

    def test_env_var_resolution(self):
        os.environ["TEST_WIKI_PATH"] = "/custom/wiki"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("version: 1\nwiki:\n  root: ${TEST_WIKI_PATH}\n")
            tmp_path = f.name

        try:
            cfg = load_yaml_config(tmp_path, resolve_env=True)
            assert cfg["wiki"]["root"] == "/custom/wiki"
        finally:
            Path(tmp_path).unlink()
            del os.environ["TEST_WIKI_PATH"]

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_yaml_config("/nonexistent/config.yaml")

    def test_empty_yaml(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            tmp_path = f.name

        try:
            cfg = load_yaml_config(tmp_path)
            assert cfg == {}
        finally:
            Path(tmp_path).unlink()


class TestLoadAllConfigs:
    def test_load_all_from_dir(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write sample config files
            Path(tmpdir, "paths.yaml").write_text(
                "version: 1\npaths:\n  wiki_root: ./wiki\n"
            )
            Path(tmpdir, "mcp.yaml").write_text(
                "version: 1\nmcp:\n  server_name: test\n"
            )

            configs = load_all_configs(tmpdir)
            assert "paths" in configs
            assert "mcp" in configs
            assert configs["paths"]["paths"]["wiki_root"] == "./wiki"

    def test_empty_dir(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            configs = load_all_configs(tmpdir)
            assert configs == {}

    def test_nonexistent_dir(self):
        configs = load_all_configs("/nonexistent/dir")
        assert configs == {}


class TestGetProviderConfig:
    def test_lookup_provider(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "providers.yaml").write_text(
                """version: 1
default_provider: main
providers:
  main:
    api_style: openai-compatible
    base_url: https://api.example.com/v1
    model: test-model
    temperature: 0.1
"""
            )
            configs = load_all_configs(tmpdir)
            provider = get_provider_config("main", configs)
            assert provider["api_style"] == "openai-compatible"
            assert provider["model"] == "test-model"

    def test_missing_provider(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "providers.yaml").write_text(
                """version: 1
providers:
  main:
    api_style: openai-compatible
"""
            )
            configs = load_all_configs(tmpdir)
            with pytest.raises(KeyError, match="nonexistent"):
                get_provider_config("nonexistent", configs)

    def test_model_env_overrides_default(self, monkeypatch):
        """model_env should override the default 'model' field when env var is set."""
        import tempfile
        monkeypatch.setenv("TEST_MODEL_OVERRIDE", "custom-model-v2")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                Path(tmpdir, "providers.yaml").write_text(
                    "version: 1\n"
                    "providers:\n"
                    "  main:\n"
                    "    api_style: openai-compatible\n"
                    "    base_url: https://example.com/v1\n"
                    "    model: text-embedding-3-small\n"
                    "    model_env: TEST_MODEL_OVERRIDE\n"
                )
                configs = load_all_configs(tmpdir)
                provider = get_provider_config("main", configs)
                assert provider["model"] == "custom-model-v2"
        finally:
            monkeypatch.delenv("TEST_MODEL_OVERRIDE", raising=False)

    def test_model_env_empty_falls_back_to_default(self, monkeypatch):
        """When model_env is set but env var is empty, default model is kept."""
        import tempfile
        monkeypatch.setenv("TEST_MODEL_OVERRIDE", "")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                Path(tmpdir, "providers.yaml").write_text(
                    "version: 1\n"
                    "providers:\n"
                    "  main:\n"
                    "    api_style: openai-compatible\n"
                    "    base_url: https://example.com/v1\n"
                    "    model: text-embedding-3-small\n"
                    "    model_env: TEST_MODEL_OVERRIDE\n"
                )
                configs = load_all_configs(tmpdir)
                provider = get_provider_config("main", configs)
                assert provider["model"] == "text-embedding-3-small"
        finally:
            monkeypatch.delenv("TEST_MODEL_OVERRIDE", raising=False)

    def test_provider_field_preserved(self):
        """New 'provider' field should be accessible from config."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "providers.yaml").write_text(
                "version: 1\n"
                "providers:\n"
                "  main:\n"
                "    provider: openai\n"
                "    api_style: openai-compatible\n"
                "    base_url: https://api.example.com/v1\n"
                "    model: test-model\n"
            )
            configs = load_all_configs(tmpdir)
            provider = get_provider_config("main", configs)
            assert provider.get("provider") == "openai"
            assert provider["model"] == "test-model"


class TestResolveEnvValue:
    """Tests for _resolve_env_value (added in v1.2.0 for $ENV_VAR support)."""

    def test_no_dollar(self, monkeypatch):
        """Plain string values pass through unchanged."""
        from paper_compass.config import _resolve_env_value
        assert _resolve_env_value("sk-12345") == "sk-12345"
        assert _resolve_env_value("https://example.com") == "https://example.com"
        assert _resolve_env_value("gpt-4o") == "gpt-4o"

    def test_dollar_var_resolved(self, monkeypatch):
        """$ENV_VAR references are resolved from os.environ."""
        from paper_compass.config import _resolve_env_value
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key-abc")
        result = _resolve_env_value("$OPENAI_API_KEY")
        assert result == "sk-real-key-abc"

    def test_dollar_var_not_set(self, monkeypatch):
        """When the referenced env var is not set, return the $VAR string as-is."""
        from paper_compass.config import _resolve_env_value
        monkeypatch.delenv("NONEXISTENT_KEY", raising=False)
        result = _resolve_env_value("$NONEXISTENT_KEY")
        assert result == "$NONEXISTENT_KEY"

    def test_empty_string(self, monkeypatch):
        """Empty string returns empty string."""
        from paper_compass.config import _resolve_env_value
        assert _resolve_env_value("") == ""

    def test_integration_with_api_key_env(self, monkeypatch):
        """Full integration: provider config resolves $ENV_VAR api_key via api_key_env."""
        import tempfile
        monkeypatch.setenv("TEST_PROVIDER_KEY", "sk-resolved-key")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                Path(tmpdir, "providers.yaml").write_text(
                    "version: 1\n"
                    "providers:\n"
                    "  main:\n"
                    "    api_style: openai-compatible\n"
                    "    base_url: https://example.com/v1\n"
                    "    model: test-model\n"
                    "    api_key_env: TEST_PROVIDER_KEY\n"
                )
                configs = load_all_configs(tmpdir)
                provider = get_provider_config("main", configs)
                assert provider["api_key"] == "sk-resolved-key"
        finally:
            monkeypatch.delenv("TEST_PROVIDER_KEY", raising=False)

    def test_integration_dollar_var_in_env_file(self, monkeypatch):
        """Simulate what happens when .env contains LLM_API_KEY=$OPENAI_API_KEY
        and get_provider_config resolves it through api_key_env -> env lookup."""

        # Simulate: env var LLM_API_KEY literally contains "$OPENAI_API_KEY"
        monkeypatch.setenv("LLM_API_KEY", "$OPENAI_API_KEY")
        # And OPENAI_API_KEY is the real key
        monkeypatch.setenv("OPENAI_API_KEY", "sk-real-deal")

        import tempfile
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                Path(tmpdir, "providers.yaml").write_text(
                    "version: 1\n"
                    "providers:\n"
                    "  main:\n"
                    "    api_style: openai-compatible\n"
                    "    base_url: https://example.com/v1\n"
                    "    model: test-model\n"
                    "    api_key_env: LLM_API_KEY\n"
                )
                configs = load_all_configs(tmpdir)
                provider = get_provider_config("main", configs)
                # _resolve_env_value reads LLM_API_KEY, sees "$OPENAI_API_KEY",
                # strips '$', looks up 'OPENAI_API_KEY' → returns "sk-real-deal"
                assert provider["api_key"] == "sk-real-deal"
        finally:
            monkeypatch.delenv("LLM_API_KEY", raising=False)
            monkeypatch.delenv("OPENAI_API_KEY", raising=False)
