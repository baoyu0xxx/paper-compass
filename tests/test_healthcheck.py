from __future__ import annotations

import importlib.util
from unittest import mock


class _ImportBlocker:
    def __init__(self, blocked: set[str]):
        self.blocked = blocked

    def __call__(self, name: str, *args, **kwargs):
        if name in self.blocked:
            raise ImportError(f"No module named '{name}'")
        return self.original(name, *args, **kwargs)


def test_cloud_embedding_healthcheck_does_not_require_sentence_transformers(monkeypatch):
    from paper_compass import healthcheck

    monkeypatch.setattr(
        healthcheck,
        "resolve_embedding_runtime",
        lambda: {
            "resolved_cloud_config": {"provider": "openai", "model": "text-embedding-3-small"},
            "local_fallback_model": "bge-base",
        },
    )

    result = healthcheck._check_local_embedding_dep()

    assert result[0] == "local_embed"
    assert result[1].startswith("SKIP")
    assert "sentence_transformers" in result[1]


def test_local_embedding_healthcheck_reports_missing_sentence_transformers(monkeypatch):
    from paper_compass import healthcheck
    import builtins

    monkeypatch.setattr(
        healthcheck,
        "resolve_embedding_runtime",
        lambda: {
            "resolved_cloud_config": None,
            "local_fallback_model": "bge-base",
        },
    )

    blocker = _ImportBlocker({"sentence_transformers"})
    blocker.original = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", blocker)

    result = healthcheck._check_local_embedding_dep()

    assert result[0] == "local_embed"
    assert result[1].startswith("WARN") or result[1].startswith("ERROR")
    assert "sentence_transformers" in result[1]


def test_bm25_dependency_check_warns_when_missing(monkeypatch):
    from paper_compass import healthcheck
    import builtins

    blocker = _ImportBlocker({"rank_bm25"})
    blocker.original = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", blocker)

    result = healthcheck._check_bm25_dep()

    assert result[0] == "bm25"
    assert result[1].startswith("WARN")
    assert "rank_bm25" in result[1]


def test_pdf_fallback_dependency_check_warns_when_missing(monkeypatch):
    from paper_compass import healthcheck
    import builtins

    blocker = _ImportBlocker({"pdfplumber"})
    blocker.original = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", blocker)

    result = healthcheck._check_pdf_fallback_dep()

    assert result[0] == "pdf_fallback"
    assert result[1].startswith("WARN")
    assert "pdfplumber" in result[1]
