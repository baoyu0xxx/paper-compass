#!/usr/bin/env python3
"""paper-compass healthcheck — verify all subsystems are operational.

Usage:
    python3 scripts/healthcheck.py           # basic checks (no API calls)
    python3 scripts/healthcheck.py --smoke    # include API connectivity probes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

# Ensure project root is on sys.path so we can import paper_compass
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ── helpers ──────────────────────────────────────────────────────────────────

Status = Tuple[str, str]  # (name, "OK" | "WARN" | "ERROR message")


def _is_unresolved_env_reference(value: str) -> bool:
    return value.startswith("$") and not __import__("os").environ.get(value[1:], "")


def _check_env() -> Status:
    """Verify .env exists and essential vars are set."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return ("env_file", "WARN: .env not found (copy from .env.example)")

    from paper_compass.env_utils import load_project_env

    load_project_env()

    import os

    missing = []
    unresolved_refs = []
    for var in (
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "VOLC_EMBED_BASE_URL",
        "VOLC_EMBED_API_KEY",
        "VOLC_EMBED_MODEL",
    ):
        val = os.environ.get(var, "")
        if not val or val in ("your_key_here", "your_endpoint_id"):
            missing.append(var)
        elif _is_unresolved_env_reference(val):
            unresolved_refs.append(f"{var} -> {val[1:]}")

    for var in ("EMBED_BASE_URL", "EMBED_API_KEY"):
        val = os.environ.get(var, "")
        if val and _is_unresolved_env_reference(val):
            unresolved_refs.append(f"{var} -> {val[1:]}")

    if missing:
        return ("env_vars", f"WARN: unset/placeholder: {', '.join(missing)}")
    if unresolved_refs:
        return ("env_vars", f"ERROR: unresolved env refs: {', '.join(unresolved_refs)}")
    return ("env_vars", "OK")


def _check_library() -> Status:
    """Verify library.json exists and is non-empty."""
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
    """Verify ChromaDB directory exists and list collections."""
    db_path = PROJECT_ROOT / "data" / "vectordb"
    if not db_path.exists():
        return ("vectordb", "WARN: not found (run build_index first)")
    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=str(db_path), settings=Settings(anonymized_telemetry=False)
        )
        cols = client.list_collections()
        names = [c.name for c in cols]
        if not names:
            return ("vectordb", "WARN: no collections found")
        return ("vectordb", f"OK ({len(names)} collections: {', '.join(names)})")
    except Exception as e:
        return ("vectordb", f"ERROR: {e}")


def _check_wiki() -> Status:
    """Verify wiki/ directory has content."""
    wiki_root = PROJECT_ROOT / "wiki"
    if not wiki_root.exists():
        return ("wiki", "WARN: wiki/ not found")
    papers = list((wiki_root / "papers").glob("*.md"))
    topics = list((wiki_root / "topics").glob("*.md"))
    total = len(papers) + len(topics)
    if total == 0:
        return ("wiki", "WARN: no markdown pages found (run ingest_to_wiki)")
    return ("wiki", f"OK ({len(papers)} papers, {len(topics)} topics)")


def _check_deps() -> Status:
    """Verify that critical Python packages are importable."""
    deps = {
        "chromadb": "chromadb",
        "pymupdf": "fitz",
        "pdfplumber": "pdfplumber",
        "rank_bm25": "rank_bm25",
        "sentence_transformers": "sentence_transformers",
        "pyyaml": "yaml",
    }
    missing = []
    for pkg_name, import_name in deps.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg_name)
    if missing:
        return ("deps", f"ERROR: missing imports: {', '.join(missing)}")
    return ("deps", "OK")


def _check_mcp_contracts() -> Status:
    """Verify MCP contracts and handlers are aligned."""
    try:
        from paper_compass.mcp_contracts import list_tools, required_params

        tools = list_tools()
        names = [t["name"] for t in tools]
        expected = {
            "search_wiki",
            "search_library",
            "ask_research",
            "get_paper_metadata",
            "search_passages",
            "save_to_wiki",
        }
        missing = sorted(expected - set(names))
        if missing:
            return ("mcp_contracts", f"ERROR: missing tools: {', '.join(missing)}")
        if len(names) != len(expected):
            return ("mcp_contracts", f"WARN: expected {len(expected)} tools, got {len(names)}")
        for t in tools:
            req = required_params(t["name"])
            if not req:
                return ("mcp_contracts", f"WARN: tool '{t['name']}' has no required params")
        return ("mcp_contracts", f"OK ({len(names)} tools)")
    except Exception as e:
        return ("mcp_contracts", f"ERROR: {e}")


def _check_config_sync() -> Status:
    """Verify repo and packaged YAML config files are in sync."""
    repo_configs = PROJECT_ROOT / "configs"
    packaged_configs = PROJECT_ROOT / "src" / "paper_compass" / "configs"
    try:
        repo_files = {p.name: p for p in repo_configs.glob("*.yaml")}
        packaged_files = {p.name: p for p in packaged_configs.glob("*.yaml")}
    except Exception as e:
        return ("config_sync", f"ERROR: {e}")

    if repo_files.keys() != packaged_files.keys():
        return (
            "config_sync",
            "ERROR: config file sets differ between repo and packaged configs",
        )

    mismatched = [
        name
        for name in sorted(repo_files)
        if repo_files[name].read_text(encoding="utf-8")
        != packaged_files[name].read_text(encoding="utf-8")
    ]
    if mismatched:
        return (
            "config_sync",
            f"ERROR: mismatched config files: {', '.join(mismatched)}",
        )
    return ("config_sync", f"OK ({len(repo_files)} yaml files synced)")


def _smoke_embedding() -> Status:
    """Probe Volcengine embedding API (one short text)."""
    import os
    import urllib.error
    import urllib.request

    from paper_compass.env_utils import load_project_env

    load_project_env()

    base_url = os.environ.get("VOLC_EMBED_BASE_URL", "")
    api_key = os.environ.get("VOLC_EMBED_API_KEY", "")
    model = os.environ.get("VOLC_EMBED_MODEL", "")

    if not all((base_url, api_key, model)):
        return ("embed_smoke", "SKIP: VOLC_EMBED_* not configured")

    payload = json.dumps(
        {
            "model": model,
            "input": [{"type": "text", "text": "healthcheck test"}],
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
        else:
            dim = len(emb.get("embedding", emb)) if emb else 0
        return ("embed_smoke", f"OK (dim={dim})")
    except urllib.error.HTTPError as e:
        return ("embed_smoke", f"ERROR: HTTP {e.code}")
    except Exception as e:
        return ("embed_smoke", f"ERROR: {e}")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="paper-compass healthcheck")
    parser.add_argument("--smoke", action="store_true", help="Include API connectivity probes")
    args = parser.parse_args()

    checks: List[Status] = []
    checks.append(_check_deps())
    checks.append(_check_env())
    checks.append(_check_library())
    checks.append(_check_vectordb())
    checks.append(_check_wiki())
    checks.append(_check_mcp_contracts())
    checks.append(_check_config_sync())

    if args.smoke:
        checks.append(_smoke_embedding())

    all_ok = True
    for name, status in checks:
        if status.startswith("ERROR"):
            icon = "✗"
            all_ok = False
        elif status.startswith("WARN"):
            icon = "⚠"
        elif status == "OK" or status.startswith("OK "):
            icon = "✓"
        else:
            icon = "?"
        print(f"  {icon} {name}: {status}")

    print()
    if all_ok:
        print("✓ All checks passed (warnings are non-blocking)")
    else:
        print("✗ Some errors detected — review above")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
