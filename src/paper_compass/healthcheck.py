"""Package-resident healthcheck entrypoint for paper-compass."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

from paper_compass.config import resolve_embedding_runtime
from paper_compass.env_utils import PROJECT_ROOT, load_project_env
from paper_compass.index_health import inspect_index_health
from paper_compass.runtime_env import runtime_state


Status = Tuple[str, str]


def _is_unresolved_env_reference(value: str) -> bool:
    return value.startswith("$") and not __import__("os").environ.get(value[1:], "")


def _check_env() -> Status:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return ("env_file", "WARN: .env not found (copy from .env.example)")

    load_project_env()

    import os

    missing = []
    unresolved_refs = []
    for var in (
        "LLM_BASE_URL",
        "LLM_API_KEY",
    ):
        val = os.environ.get(var, "")
        if not val or val in ("your_key_here", "your_endpoint_id"):
            missing.append(var)
        elif _is_unresolved_env_reference(val):
            unresolved_refs.append(f"{var} -> {val[1:]}")

    for var in (
        "VOLC_EMBED_BASE_URL",
        "VOLC_EMBED_API_KEY",
        "VOLC_EMBED_MODEL",
        "EMBED_BASE_URL",
        "EMBED_API_KEY",
        "EMBED_MODEL",
        "LOCAL_EMBED_MODEL",
    ):
        val = os.environ.get(var, "")
        if val and _is_unresolved_env_reference(val):
            unresolved_refs.append(f"{var} -> {val[1:]}")

    if missing:
        return ("env_vars", f"WARN: unset/placeholder: {', '.join(missing)}")
    if unresolved_refs:
        return ("env_vars", f"ERROR: unresolved env refs: {', '.join(unresolved_refs)}")
    return ("env_vars", "OK")


def _check_library() -> Status:
    lib_path = PROJECT_ROOT / "data" / "zotero-export" / "library.json"
    if not lib_path.exists():
        return ("library.json", "WARN: not found (run sync_zotero first)")
    try:
        with open(lib_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        if not records:
            return ("library.json", "WARN: empty file")
        return ("library.json", f"OK ({len(records)} records)")
    except Exception as e:
        return ("library.json", f"ERROR: {e}")


def _check_vectordb() -> Status:
    db_path = PROJECT_ROOT / "data" / "vectordb"
    if not db_path.exists():
        return ("vectordb", "WARN: not found (run build_index first)")
    try:
        report = inspect_index_health(db_path)
        if report.severity == "corrupted":
            return ("vectordb", f"ERROR: {report.summary}")
        if report.severity == "warning":
            return ("vectordb", f"WARN: {report.summary}")
        names = list(report.collection_counts.keys())
        if not names:
            return ("vectordb", "WARN: no collections found")
        return ("vectordb", f"OK ({len(names)} collections: {', '.join(names)})")
    except Exception as e:
        return ("vectordb", f"ERROR: {e}")


def _check_wiki() -> Status:
    wiki_root = PROJECT_ROOT / "wiki"
    if not wiki_root.exists():
        return ("wiki", "WARN: wiki/ not found")
    papers = list((wiki_root / "papers").glob("*.md"))
    topics = list((wiki_root / "topics").glob("*.md"))
    total = len(papers) + len(topics)
    if total == 0:
        return ("wiki", "WARN: no markdown pages found (run ingest_to_wiki)")
    return ("wiki", f"OK ({len(papers)} papers, {len(topics)} topics)")


def _check_core_deps() -> Status:
    deps = {
        "chromadb": "chromadb",
        "pymupdf": "fitz",
        "pyyaml": "yaml",
    }
    missing = []
    for pkg_name, import_name in deps.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg_name)
    if missing:
        return ("core_deps", f"ERROR: missing imports: {', '.join(missing)}")
    return ("core_deps", "OK")


def _check_bm25_dep() -> Status:
    try:
        __import__("rank_bm25")
        return ("bm25", "OK")
    except ImportError:
        return (
            "bm25",
            "WARN: rank_bm25 missing; hybrid/BM25 retrieval will degrade to semantic-only search",
        )


def _check_pdf_fallback_dep() -> Status:
    try:
        __import__("pdfplumber")
        return ("pdf_fallback", "OK")
    except ImportError:
        return (
            "pdf_fallback",
            "WARN: pdfplumber missing; PyMuPDF remains available but PDF fallback extraction is disabled",
        )


def _check_markitdown_dep() -> Status:
    try:
        __import__("markitdown")
        return ("markitdown", "OK")
    except ImportError:
        return (
            "markitdown",
            "WARN: markitdown missing; non-PDF document extraction is unavailable",
        )


def _check_local_embedding_dep() -> Status:
    runtime = resolve_embedding_runtime()
    if runtime.get("resolved_cloud_config"):
        return (
            "local_embed",
            "SKIP: cloud embedding configured; sentence_transformers not required unless local fallback is used",
        )

    try:
        __import__("sentence_transformers")
        return ("local_embed", f"OK ({runtime.get('local_fallback_model', 'bge-base')})")
    except ImportError:
        return (
            "local_embed",
            "WARN: sentence_transformers missing; local embedding fallback is unavailable",
        )


def _check_runtime() -> Status:
    state = runtime_state(project_root=PROJECT_ROOT)
    if state.status == "active":
        return ("runtime", f"OK ({state.managed_python})")
    if state.status == "missing":
        return ("runtime", "WARN: managed runtime not initialized; run python scripts/bootstrap_runtime.py")
    return ("runtime", f"ERROR: {'; '.join(state.reasons)}")


def _check_mcp_contracts() -> Status:
    try:
        from paper_compass.mcp_contracts import list_tools, required_params
        from paper_compass.mcp_server import _HANDLERS  # noqa: F401

        tools = list_tools()
        names = [t["name"] for t in tools]
        expected_count = 6
        if len(names) != expected_count:
            return ("mcp_contracts", f"WARN: expected {expected_count} tools, got {len(names)}")
        for t in tools:
            req = required_params(t["name"])
            if not req:
                return ("mcp_contracts", f"WARN: tool '{t['name']}' has no required params")
        return ("mcp_contracts", "OK")
    except Exception as e:
        return ("mcp_contracts", f"ERROR: {e}")


def _smoke_embedding() -> Status:
    import os

    load_project_env()
    runtime = resolve_embedding_runtime()
    resolved = runtime.get("resolved_cloud_config")

    if not resolved:
        local_model = runtime.get("local_fallback_model", "bge-base")
        return ("embed_smoke", f"SKIP: no cloud embedding configured (local fallback: {local_model})")

    import urllib.error
    import urllib.request

    provider = resolved.get("provider", "openai")
    base_url = resolved.get("base_url", "")
    api_key = resolved.get("api_key", "")
    model = resolved.get("model", "")

    if not all((base_url, api_key, model)):
        return ("embed_smoke", "ERROR: resolved embedding provider is missing base_url/api_key/model")

    if provider == "volcengine":
        payload = json.dumps(
            {
                "model": model,
                "input": [{"type": "text", "text": "healthcheck test"}],
            }
        ).encode("utf-8")
    else:
        payload = json.dumps(
            {
                "model": model,
                "input": ["healthcheck test"],
            }
        ).encode("utf-8")

    req = urllib.request.Request(
        base_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        emb = data.get("data", {})
        if isinstance(emb, dict):
            dim = len(emb.get("embedding", []))
        elif isinstance(emb, list) and emb:
            first = emb[0] if emb else {}
            dim = len(first.get("embedding", [])) if isinstance(first, dict) else 0
        else:
            dim = 0
        return ("embed_smoke", f"OK ({provider}, dim={dim})")
    except urllib.error.HTTPError as e:
        return ("embed_smoke", f"ERROR: HTTP {e.code}")
    except Exception as e:
        return ("embed_smoke", f"ERROR: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="paper-compass healthcheck")
    parser.add_argument("--smoke", action="store_true", help="Include API connectivity probes")
    parser.add_argument(
        "--deps-only",
        action="store_true",
        help="Only check Python dependencies; skip env, data, vectordb, wiki, MCP, and API probes",
    )
    args = parser.parse_args()

    checks: List[Status] = []
    checks.append(_check_core_deps())
    checks.append(_check_bm25_dep())
    checks.append(_check_pdf_fallback_dep())
    checks.append(_check_markitdown_dep())
    checks.append(_check_local_embedding_dep())

    if not args.deps_only:
        checks.append(_check_runtime())
        checks.append(_check_env())
        checks.append(_check_library())
        checks.append(_check_vectordb())
        checks.append(_check_wiki())
        checks.append(_check_mcp_contracts())

    if args.smoke and not args.deps_only:
        checks.append(_smoke_embedding())

    all_ok = True
    for name, status in checks:
        if status.startswith("ERROR"):
            icon = "✗"
            all_ok = False
        elif status.startswith("WARN"):
            icon = "⚠"
        elif status.startswith("SKIP"):
            icon = "↷"
        elif status == "OK" or status.startswith("OK "):
            icon = "✓"
        else:
            icon = "?"
        print(f"  {icon} {name}: {status}")

    print()
    if all_ok:
        print("✓ All blocking checks passed (warnings are non-blocking)")
    else:
        print("✗ Some blocking errors detected — review above")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
