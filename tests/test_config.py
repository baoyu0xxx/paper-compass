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
