import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD_INDEX_PATH = ROOT / "scripts" / "build_index.py"


@pytest.fixture
def build_index_module():
    spec = importlib.util.spec_from_file_location("paper_compass_build_index_test", BUILD_INDEX_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_init_embedder_uses_provider_dimension(monkeypatch, build_index_module):
    monkeypatch.setattr(build_index_module, "load_project_env", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        build_index_module,
        "resolve_embedding_runtime",
        lambda *_args, **_kwargs: {
            "resolved_provider": "embedding_main",
            "resolved_cloud_config": {
                "provider": "openai",
                "base_url": "https://embed.example.com/v1/embeddings",
                "api_key": "sk-test",
                "model": "custom-embed",
                "dimension": 3072,
            },
            "local_fallback_model": "bge-base",
        },
    )

    embedder = build_index_module._init_embedder()

    assert embedder.model_id == "openai:custom-embed"
    assert embedder.dimension == 3072


def test_init_embedder_uses_local_model_env_on_fallback(monkeypatch, build_index_module):
    monkeypatch.setattr(build_index_module, "load_project_env", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        build_index_module,
        "resolve_embedding_runtime",
        lambda *_args, **_kwargs: {
            "resolved_provider": None,
            "resolved_cloud_config": None,
            "local_fallback_model": "minilm",
        },
    )
    monkeypatch.setenv("LOCAL_EMBED_MODEL", "minilm")

    embedder = build_index_module._init_embedder()

    assert embedder.model_id == "minilm"
    assert embedder.dimension == 384


def test_validate_reports_local_fallback_without_cloud_provider(monkeypatch):
    from paper_compass.cli import validate as validate_mod

    monkeypatch.setattr(validate_mod, "load_all_configs", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        validate_mod,
        "resolve_embedding_runtime",
        lambda *_args, **_kwargs: {
            "resolved_provider": None,
            "resolved_cloud_config": None,
            "local_fallback_model": "bge-base",
        },
    )
    monkeypatch.delenv("LOCAL_EMBED_MODEL", raising=False)

    name, status = validate_mod._test_embedding()

    assert name == "embed"
    assert status.startswith("OK (local fallback configured: bge-base")
