"""paper-compass status subcommand.

Summarize resolved config, local data assets, vector index state, and sync runtime state.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from paper_compass.config import (
    get_embedding_provider_order,
    get_provider_config,
    load_all_configs,
    resolve_embedding_runtime,
)
from paper_compass.env_utils import DEFAULT_ENV_PATH, PROJECT_ROOT, load_project_env
from paper_compass.index_health import inspect_index_health
from paper_compass.local_state import source_config_path
from paper_compass.pipeline_sync import _state_path, inspect_sync_lock
from paper_compass.resources import project_root
from paper_compass.runtime_env import runtime_state
from paper_compass.wiki_gen import describe_wiki_prompt_bundle


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


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_sync_status() -> dict[str, Any]:
    last_sync = _read_json_file(_state_path(PROJECT_ROOT))
    lock_status = inspect_sync_lock(PROJECT_ROOT)
    source_payload = _read_json_file(source_config_path(PROJECT_ROOT))
    zotero_source = source_payload.get("zotero") if isinstance(source_payload.get("zotero"), dict) else {}
    return {
        "last_sync": {
            "status": str(last_sync.get("status", "") or ""),
            "stage": str(last_sync.get("stage", "") or ""),
            "run_id": str(last_sync.get("run_id", "") or ""),
            "started_at": last_sync.get("started_at"),
            "updated_at": last_sync.get("updated_at"),
            "finished_at": last_sync.get("finished_at"),
        },
        "lock": {
            "exists": lock_status.exists,
            "stale": lock_status.stale,
            "reason": lock_status.reason,
            "path": str(lock_status.path),
        },
        "last_successful_zotero_source": {
            "db_path": str(zotero_source.get("db_path", "") or ""),
            "storage_path": str(zotero_source.get("storage_path", "") or ""),
            "source_kind": str(zotero_source.get("source_kind", "") or ""),
            "is_live_candidate": bool(zotero_source.get("is_live_candidate", False)),
        },
    }


def _detect_embed_cascade(configs: dict[str, Any]) -> list[str]:
    cascade: list[str] = []
    try:
        ordered = get_embedding_provider_order(configs)
    except ValueError as exc:
        return [f"INVALID: {exc}"]

    for provider_name in ordered:
        cfg = _safe_provider(provider_name, configs)
        if cfg is None:
            continue
        cascade.append(f"{provider_name} ({cfg.get('provider', 'openai')}:{cfg.get('model', '')})")
    cascade.append(f"local ({(os.environ.get('LOCAL_EMBED_MODEL', 'bge-base').strip() or 'bge-base')})")
    return cascade


def collect_status() -> dict[str, Any]:
    load_project_env()
    configs = load_all_configs()

    repo_root = project_root()
    env_path = DEFAULT_ENV_PATH
    env_loaded = env_path.exists() and env_path.is_file()

    llm_cfg = _safe_provider("wiki_generation", configs) or {}

    try:
        embedding_runtime = resolve_embedding_runtime(configs)
    except (ValueError, KeyError) as exc:
        embedding_runtime = {
            "role": "embedding",
            "config_source": "invalid",
            "selected_provider": "n.a.",
            "resolved_provider": None,
            "resolved_cloud_config": None,
            "candidate_order": [],
            "display_cascade": [f"INVALID ({exc})"],
            "local_fallback_model": os.environ.get("LOCAL_EMBED_MODEL", "bge-base").strip() or "bge-base",
            "legacy_fields": [],
            "configured_candidates": [],
            "error": str(exc),
        }

    masked_candidates = []
    for entry in embedding_runtime.get("configured_candidates", []):
        masked_candidates.append({**entry, "api_key": _mask_secret(entry.get("api_key", ""))})

    prompt_bundle = describe_wiki_prompt_bundle()

    library_path = PROJECT_ROOT / "data" / "zotero-export" / "library.json"
    wiki_root = PROJECT_ROOT / "wiki"
    db_path = PROJECT_ROOT / "data" / "vectordb"

    health = inspect_index_health(db_path)
    runtime = runtime_state(project_root=PROJECT_ROOT)
    sync_status = _read_sync_status()

    return {
        "project_root": str(repo_root),
        "package_project_root": str(PROJECT_ROOT),
        "env_path": str(env_path),
        "env_loaded": env_loaded,
        "runtime": {
            "status": runtime.status,
            "managed_venv": str(runtime.managed_venv),
            "managed_python": str(runtime.managed_python),
            "current_python": str(runtime.current_python),
            "python_version": runtime.current_python_version,
            "reasons": runtime.reasons,
        },
        "llm": {
            "provider": llm_cfg.get("provider", ""),
            "base_url": llm_cfg.get("base_url", ""),
            "model": llm_cfg.get("model", ""),
            "api_key": _mask_secret(llm_cfg.get("api_key", "")),
        },
        "embedding": {
            "role": embedding_runtime.get("role", "embedding"),
            "config_source": embedding_runtime.get("config_source", "unknown"),
            "selected_provider": embedding_runtime.get("selected_provider", ""),
            "resolved_provider": embedding_runtime.get("resolved_provider"),
            "local_fallback_model": embedding_runtime.get("local_fallback_model", "bge-base"),
            "display_cascade": embedding_runtime.get("display_cascade", []),
            "legacy_fields": embedding_runtime.get("legacy_fields", []),
            "configured_candidates": masked_candidates,
        },
        "wiki_prompt": prompt_bundle,
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
        "sync": sync_status,
    }


def _print_status_report(status: dict[str, Any]) -> None:
    print()
    print("  paper-compass status")
    print()
    print(f"  project root: {status['project_root']}")
    print(f"  package root: {status['package_project_root']}")
    print(f"  env path: {status['env_path']} ({'present' if status['env_loaded'] else 'missing'})")
    print()

    runtime = status["runtime"]
    print("  runtime")
    print(f"    status: {runtime['status']}")
    print(f"    managed venv: {runtime['managed_venv']}")
    print(f"    managed python: {runtime['managed_python']}")
    print(f"    current python: {runtime['current_python']}")
    print(f"    python version: {runtime['python_version'] or 'unknown'}")
    for reason in runtime.get("reasons", []):
        print(f"    note: {reason}")
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
    print(
        f"    embedding role: {embed['role']} | source={embed['config_source']} | selected={embed['selected_provider'] or 'n.a.'} | active={embed['resolved_provider'] or 'local'}"
    )
    print(f"    local fallback: {embed['local_fallback_model']}")
    print(f"    cascade: {' -> '.join(embed['display_cascade'])}")
    if embed["legacy_fields"]:
        print(f"    legacy fields: {', '.join(embed['legacy_fields'])}")
    for candidate in embed["configured_candidates"]:
        print(
            f"    - {candidate['name']}: {candidate['provider'] or 'n.a.'} | {candidate['base_url'] or 'n.a.'} | {candidate['model'] or 'n.a.'} | {candidate['api_key']}"
        )
    print()

    prompt = status["wiki_prompt"]
    print("  wiki prompt")
    print(
        f"    prompt bundle: {prompt['mode']} | selection={prompt['selection']} | dir={prompt['prompt_dir']}"
    )
    print(
        f"    files: router={prompt['router_loaded']} overview={prompt['overview_loaded']} empirical={prompt['empirical_loaded']} fallback={prompt['fallback_loaded']}"
    )
    if prompt.get("reason"):
        print(f"    note: {prompt['reason']}")
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
    print()

    sync = status["sync"]
    print("  sync")
    print(
        f"    last status: {sync['last_sync'].get('status') or 'unknown'} | stage={sync['last_sync'].get('stage') or 'unknown'}"
    )
    if sync["last_sync"].get("run_id"):
        print(f"    run id: {sync['last_sync']['run_id']}")
    if sync["last_sync"].get("started_at"):
        print(f"    started at: {sync['last_sync']['started_at']}")
    if sync["last_sync"].get("updated_at"):
        print(f"    updated at: {sync['last_sync']['updated_at']}")
    if sync["last_sync"].get("finished_at"):
        print(f"    finished at: {sync['last_sync']['finished_at']}")
    print(
        f"    lock: stale={'yes' if sync['lock'].get('stale') else 'no'} | exists={'yes' if sync['lock'].get('exists') else 'no'} | path={sync['lock'].get('path') or 'n.a.'}"
    )
    if sync["lock"].get("reason"):
        print(f"    lock reason: {sync['lock']['reason']}")
    source = sync["last_successful_zotero_source"]
    if source.get("db_path"):
        print(f"    zotero source: {source['db_path']}")
        print(f"    storage: {source.get('storage_path') or 'n.a.'}")
        print(f"    source kind: {source.get('source_kind') or 'unknown'} | live candidate={'yes' if source.get('is_live_candidate') else 'no'}")
    else:
        print("    zotero source: unavailable")


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
