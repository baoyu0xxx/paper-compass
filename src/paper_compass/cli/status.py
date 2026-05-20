"""paper-compass status subcommand.

Summarize resolved config, local data assets, and vector index state.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from paper_compass.config import get_provider_config, load_all_configs
from paper_compass.env_utils import DEFAULT_ENV_PATH, PROJECT_ROOT, load_project_env
from paper_compass.index_health import inspect_index_health
from paper_compass.resources import project_root


def _mask_secret(value: str) -> str:
    if not value:
        return "missing"
    if len(value) <= 8:
        return f"configured ({len(value)} chars)"
    return f"{value[:4]}...{value[-4:]} ({len(value)} chars)"


def _safe_provider(provider_name: str, configs: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return get_provider_config(provider_name, configs)
    except Exception:
        return None


def _read_library_count(library_path: Path) -> int | None:
    if not library_path.exists() or not library_path.is_file():
        return None
    try:
        payload = json.loads(library_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return len(payload) if isinstance(payload, list) else None


def _count_markdown_pages(wiki_root: Path) -> dict[str, int]:
    if not wiki_root.exists() or not wiki_root.is_dir():
        return {}
    counts: dict[str, int] = {}
    for section in ["papers", "topics", "methods", "comparisons", "queries"]:
        section_dir = wiki_root / section
        if section_dir.exists() and section_dir.is_dir():
            counts[section] = len(list(section_dir.glob("*.md")))
    return counts


def _list_vectordb_collections(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists() or not db_path.is_dir():
        return []
    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(path=str(db_path), settings=Settings(anonymized_telemetry=False))
        collections = []
        for collection in client.list_collections():
            meta = collection.metadata or {}
            collections.append(
                {
                    "name": collection.name,
                    "count": int(collection.count()),
                    "embedding_model": meta.get("embedding_model", ""),
                }
            )
        return collections
    except Exception as exc:
        return [{"name": "<error>", "count": 0, "embedding_model": str(exc)}]


def _detect_embed_cascade(configs: dict[str, Any]) -> list[str]:
    cascade: list[str] = []
    main_cfg = _safe_provider("embedding_main", configs)
    volc_cfg = _safe_provider("embedding_volcengine", configs)
    if main_cfg is not None:
        cascade.append(f"embedding_main ({main_cfg.get('provider', 'openai')}:{main_cfg.get('model', '')})")
    if volc_cfg is not None:
        cascade.append(f"embedding_volcengine ({volc_cfg.get('provider', 'openai')}:{volc_cfg.get('model', '')})")
    cascade.append(f"local ({(os.environ.get('LOCAL_EMBED_MODEL', 'bge-base').strip() or 'bge-base')})")
    return cascade


def collect_status() -> dict[str, Any]:
    load_project_env()
    configs = load_all_configs()

    repo_root = project_root()
    env_path = DEFAULT_ENV_PATH
    env_loaded = env_path.exists() and env_path.is_file()

    llm_cfg = _safe_provider("wiki_generation", configs) or {}
    embed_main_cfg = _safe_provider("embedding_main", configs) or {}
    embed_volc_cfg = _safe_provider("embedding_volcengine", configs) or {}

    library_path = PROJECT_ROOT / "data" / "zotero-export" / "library.json"
    wiki_root = PROJECT_ROOT / "wiki"
    db_path = PROJECT_ROOT / "data" / "vectordb"

    health = inspect_index_health(db_path)

    return {
        "project_root": str(repo_root),
        "package_project_root": str(PROJECT_ROOT),
        "env_path": str(env_path),
        "env_loaded": env_loaded,
        "llm": {
            "provider": llm_cfg.get("provider", ""),
            "base_url": llm_cfg.get("base_url", ""),
            "model": llm_cfg.get("model", ""),
            "api_key": _mask_secret(llm_cfg.get("api_key", "")),
        },
        "embedding": {
            "main": {
                "provider": embed_main_cfg.get("provider", ""),
                "base_url": embed_main_cfg.get("base_url", ""),
                "model": embed_main_cfg.get("model", ""),
                "api_key": _mask_secret(embed_main_cfg.get("api_key", "")),
            },
            "volcengine": {
                "provider": embed_volc_cfg.get("provider", ""),
                "base_url": embed_volc_cfg.get("base_url", ""),
                "model": embed_volc_cfg.get("model", ""),
                "api_key": _mask_secret(embed_volc_cfg.get("api_key", "")),
            },
            "local_fallback_model": os.environ.get("LOCAL_EMBED_MODEL", "bge-base").strip() or "bge-base",
            "cascade_order": _detect_embed_cascade(configs),
        },
        "library": {
            "path": str(library_path),
            "record_count": _read_library_count(library_path),
        },
        "wiki": {
            "root": str(wiki_root),
            "page_counts": _count_markdown_pages(wiki_root),
        },
        "vectordb": {
            "path": str(db_path),
            "health": {
                "severity": health.severity,
                "summary": health.summary,
                "recommended_action": health.recommended_action,
            },
            "collections": _list_vectordb_collections(db_path),
        },
    }


def _print_status_report(status: dict[str, Any]) -> None:
    print()
    print("  paper-compass status")
    print()
    print(f"  project root: {status['project_root']}")
    print(f"  package root: {status['package_project_root']}")
    print(f"  env path: {status['env_path']} ({'present' if status['env_loaded'] else 'missing'})")
    print()

    llm = status["llm"]
    print("  LLM")
    print(f"    provider: {llm['provider'] or 'n.a.'}")
    print(f"    base_url: {llm['base_url'] or 'n.a.'}")
    print(f"    model: {llm['model'] or 'n.a.'}")
    print(f"    api_key: {llm['api_key']}")
    print()

    embed = status["embedding"]
    print("  embedding")
    print(f"    main: {embed['main']['provider'] or 'n.a.'} | {embed['main']['base_url'] or 'n.a.'} | {embed['main']['model'] or 'n.a.'} | {embed['main']['api_key']}")
    print(f"    volcengine: {embed['volcengine']['provider'] or 'n.a.'} | {embed['volcengine']['base_url'] or 'n.a.'} | {embed['volcengine']['model'] or 'n.a.'} | {embed['volcengine']['api_key']}")
    print(f"    local fallback: {embed['local_fallback_model']}")
    print(f"    cascade: {' -> '.join(embed['cascade_order'])}")
    print()

    library = status["library"]
    print("  library")
    print(f"    path: {library['path']}")
    print(f"    records: {library['record_count'] if library['record_count'] is not None else 'unavailable'}")
    print()

    wiki = status["wiki"]
    print("  wiki")
    print(f"    root: {wiki['root']}")
    if wiki["page_counts"]:
        counts = ", ".join(f"{key}={value}" for key, value in wiki["page_counts"].items())
        print(f"    pages: {counts}")
    else:
        print("    pages: unavailable")
    print()

    vectordb = status["vectordb"]
    print("  vectordb")
    print(f"    path: {vectordb['path']}")
    print(f"    health: {vectordb['health']['severity']} | {vectordb['health']['summary']}")
    print(f"    action: {vectordb['health']['recommended_action']}")
    if vectordb["collections"]:
        for collection in vectordb["collections"]:
            print(
                f"    - {collection['name']}: count={collection['count']} | embedding_model={collection['embedding_model']}"
            )
    else:
        print("    - no collections")


def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "status",
        help="Show resolved config, local data assets, and vector index state",
        description="Summarize resolved configuration and local paper-compass runtime state.",
    )
    parser.add_argument("--json", action="store_true", help="Print raw JSON output")
    parser.set_defaults(func=execute_status)


def execute_status(args: argparse.Namespace) -> int:
    status = collect_status()
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        _print_status_report(status)
    return 0
