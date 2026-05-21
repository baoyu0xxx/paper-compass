import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUILD_INDEX_PATH = ROOT / "scripts" / "build_index.py"


@pytest.fixture
def build_index_module():
    spec = importlib.util.spec_from_file_location("paper_compass_build_index_role_test", BUILD_INDEX_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_init_embedder_accepts_single_shared_embedding_role(monkeypatch, build_index_module):
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
                "model": "text-embedding-3-small",
                "dimension": 1536,
            },
            "local_fallback_model": "bge-base",
        },
    )

    embedder = build_index_module._init_embedder()

    assert embedder.model_id == "openai:text-embedding-3-small"
    assert embedder.dimension == 1536
