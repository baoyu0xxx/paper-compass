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


def test_healthcheck_deps_only_skips_project_state_checks(monkeypatch, capsys):
    from paper_compass import healthcheck

    calls = []

    monkeypatch.setattr(healthcheck, "_check_core_deps", lambda: calls.append("core") or ("core_deps", "OK"))
    monkeypatch.setattr(healthcheck, "_check_bm25_dep", lambda: calls.append("bm25") or ("bm25", "OK"))
    monkeypatch.setattr(healthcheck, "_check_pdf_fallback_dep", lambda: calls.append("pdf") or ("pdf_fallback", "OK"))
    monkeypatch.setattr(healthcheck, "_check_local_embedding_dep", lambda: calls.append("local") or ("local_embed", "SKIP: cloud embedding configured"))
    monkeypatch.setattr(healthcheck, "_check_runtime", lambda: calls.append("runtime") or ("runtime", "OK"))
    monkeypatch.setattr(healthcheck, "_check_env", lambda: calls.append("env") or ("env_vars", "OK"))
    monkeypatch.setattr(healthcheck, "_check_library", lambda: calls.append("library") or ("library.json", "OK"))
    monkeypatch.setattr(healthcheck, "_check_vectordb", lambda: calls.append("vectordb") or ("vectordb", "OK"))
    monkeypatch.setattr(healthcheck, "_check_wiki", lambda: calls.append("wiki") or ("wiki", "OK"))
    monkeypatch.setattr(healthcheck, "_check_mcp_contracts", lambda: calls.append("mcp") or ("mcp_contracts", "OK"))
    monkeypatch.setattr("sys.argv", ["paper-compass-healthcheck", "--deps-only"])

    rc = healthcheck.main()

    assert rc == 0
    assert calls == ["core", "bm25", "pdf", "local"]
    output = capsys.readouterr().out
    assert "core_deps" in output
    assert "runtime" not in output
    assert "library.json" not in output
    assert "vectordb" not in output


def test_healthcheck_includes_runtime_check_in_normal_mode(monkeypatch, capsys):
    from paper_compass import healthcheck

    calls = []

    monkeypatch.setattr(healthcheck, "_check_core_deps", lambda: ("core_deps", "OK"))
    monkeypatch.setattr(healthcheck, "_check_bm25_dep", lambda: ("bm25", "OK"))
    monkeypatch.setattr(healthcheck, "_check_pdf_fallback_dep", lambda: ("pdf_fallback", "OK"))
    monkeypatch.setattr(healthcheck, "_check_local_embedding_dep", lambda: ("local_embed", "OK"))
    monkeypatch.setattr(healthcheck, "_check_runtime", lambda: calls.append("runtime") or ("runtime", "OK"))
    monkeypatch.setattr(healthcheck, "_check_env", lambda: ("env_vars", "OK"))
    monkeypatch.setattr(healthcheck, "_check_library", lambda: ("library.json", "OK"))
    monkeypatch.setattr(healthcheck, "_check_vectordb", lambda: ("vectordb", "OK"))
    monkeypatch.setattr(healthcheck, "_check_wiki", lambda: ("wiki", "OK"))
    monkeypatch.setattr(healthcheck, "_check_mcp_contracts", lambda: ("mcp_contracts", "OK"))
    monkeypatch.setattr("sys.argv", ["paper-compass-healthcheck"])

    rc = healthcheck.main()

    assert rc == 0
    assert calls == ["runtime"]
    assert "runtime: OK" in capsys.readouterr().out


def test_vectordb_healthcheck_reports_index_health_corruption(monkeypatch):
    from types import SimpleNamespace
    from paper_compass import healthcheck

    monkeypatch.setattr(
        healthcheck,
        "inspect_index_health",
        lambda path: SimpleNamespace(
            severity="corrupted",
            summary="hnsw index load failed",
            collection_counts={},
            manifest_files=[],
        ),
    )

    name, status = healthcheck._check_vectordb()

    assert name == "vectordb"
    assert status == "ERROR: hnsw index load failed"
