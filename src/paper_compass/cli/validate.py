"""paper-compass validate subcommand.

Tests connectivity for configured LLM and embedding providers.
Produces a readable status report.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from paper_compass.config import get_provider_config, load_all_configs
from paper_compass.env_utils import (
    DEFAULT_ENV_PATH,
    PROJECT_ROOT,
    load_project_env,
)

logger = logging.getLogger(__name__)


def _is_unresolved_env_reference(value: str) -> bool:
    return value.startswith("$") and not os.environ.get(value[1:], "")


def _check_dotenv(env_path: str) -> tuple[str, str]:
    """Check .env file exists and has required vars."""
    path = Path(env_path)
    if not path.exists():
        return ("dotenv", "ERROR: .env not found (run `paper-compass init`)")

    load_project_env(path)

    missing = []
    placeholders = []
    unresolved_refs = []
    for var in ("LLM_BASE_URL", "LLM_API_KEY", "EMBED_BASE_URL", "EMBED_API_KEY", "VOLC_EMBED_BASE_URL", "VOLC_EMBED_API_KEY"):
        val = os.environ.get(var, "")
        if not val:
            if var in ("LLM_BASE_URL", "LLM_API_KEY"):
                missing.append(var)
        elif val in ("your_key_here", "sk-your-key-here"):
            placeholders.append(var)
        elif _is_unresolved_env_reference(val):
            unresolved_refs.append(f"{var} -> {val[1:]}")

    # Check embedding vars (either openai or volcengine)
    has_openai_embed = bool(os.environ.get("EMBED_BASE_URL")) and bool(
        os.environ.get("EMBED_API_KEY")
    )
    has_volc_embed = bool(os.environ.get("VOLC_EMBED_BASE_URL")) and bool(
        os.environ.get("VOLC_EMBED_API_KEY")
    )
    if not has_openai_embed and not has_volc_embed:
        missing.extend(["EMBED_* or VOLC_EMBED_* (at least one embedding provider)"])

    if missing:
        return ("dotenv", f"ERROR: missing: {', '.join(missing)}")
    if unresolved_refs:
        return ("dotenv", f"ERROR: unresolved env refs: {', '.join(unresolved_refs)}")
    if placeholders:
        return ("dotenv", f"WARN: placeholder values: {', '.join(placeholders)}")
    return ("dotenv", "OK")


def _test_llm() -> tuple[str, str]:
    """Test LLM API connectivity."""
    try:
        configs = load_all_configs()
        provider = get_provider_config("wiki_generation", configs)
    except (KeyError, FileNotFoundError) as e:
        return ("llm", f"ERROR: config load failed: {e}")

    base_url = provider.get("base_url", "").rstrip("/")
    api_key = provider.get("api_key", "")
    model = provider.get("model", "unknown")

    if not base_url or not api_key:
        return ("llm", "SKIP: base_url or api_key not configured")

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        start = time.time()
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = time.time() - start
            result = json.loads(resp.read().decode("utf-8"))
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        status = f"OK (model: {model}, {elapsed:.1f}s, response: {len(content)} chars)"
        return ("llm", status)
    except urllib.error.HTTPError as e:
        return ("llm", f"ERROR: HTTP {e.code} - {e.reason}")
    except Exception as e:
        return ("llm", f"ERROR: {e}")


def _test_embedding() -> tuple[str, str]:
    """Test embedding API connectivity via the configured provider cascade."""
    try:
        configs = load_all_configs()
        # Try main embedding first, fall back to volcengine
        for pkey in ["embedding_main", "embedding_volcengine"]:
            try:
                provider = get_provider_config(pkey, configs)
                if provider.get("base_url") and provider.get("api_key"):
                    break
            except KeyError:
                continue
        else:
            local_model = os.environ.get("LOCAL_EMBED_MODEL", "bge-base").strip() or "bge-base"
            try:
                from paper_compass.embedder import Embedder

                embedder = Embedder()
                embedder.configure_local(local_model)
                return (
                    "embed",
                    f"OK (local fallback configured: {local_model}, dim={embedder.dimension}; no cloud provider configured)",
                )
            except Exception as e:
                return (
                    "embed",
                    f"WARN: no cloud provider configured; local fallback '{local_model}' unavailable: {e}",
                )
    except FileNotFoundError as e:
        return ("embed", f"ERROR: config load failed: {e}")

    base_url = provider.get("base_url", "").rstrip("/")
    api_key = provider.get("api_key", "")
    model = provider.get("model", "unknown")
    is_volc = provider.get("provider") == "volcengine"

    if not base_url or not api_key:
        return ("embed", "SKIP: base_url or api_key not configured")

    if is_volc:
        payload = json.dumps({
            "model": model,
            "input": [{"type": "text", "text": "healthcheck ping"}],
        }).encode("utf-8")
    else:
        payload = json.dumps({
            "model": model,
            "input": ["healthcheck ping"],
        }).encode("utf-8")

    req = urllib.request.Request(
        base_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        start = time.time()
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = time.time() - start
            result = json.loads(resp.read().decode("utf-8"))
        data = result.get("data")
        if isinstance(data, dict):
            emb = data.get("embedding", [])
            dim = len(emb) if emb else 0
        elif isinstance(data, list) and data:
            emb = data[0].get("embedding", [])
            dim = len(emb) if emb else 0
        else:
            dim = 0
        status = f"OK (model: {model}, dim={dim}, {elapsed:.1f}s)"
        return ("embed", status)
    except urllib.error.HTTPError as e:
        return ("embed", f"ERROR: HTTP {e.code} - {e.reason}")
    except Exception as e:
        return ("embed", f"ERROR: {e}")


# ── Entry for top-level CLI dispatch ────────────────────────────────────


def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add 'validate' subcommand to the top-level paper-compass CLI."""
    parser = subparsers.add_parser(
        "validate",
        help="Test connectivity and configuration",
        description="Validate paper-compass configuration and test API connectivity.",
    )
    parser.add_argument(
        "--env-path",
        default=str(DEFAULT_ENV_PATH),
        help=f"Path to .env file (default: {DEFAULT_ENV_PATH})",
    )
    parser.set_defaults(func=execute_validate)


def execute_validate(args: argparse.Namespace) -> int:
    """Execute the validate subcommand."""
    env_path = args.env_path

    print()
    print("  paper-compass validation")
    print()

    load_project_env(env_path)
    configs = load_all_configs()

    try:
        llm_provider = get_provider_config("wiki_generation", configs)
    except Exception:
        llm_provider = {}

    try:
        embed_main_provider = get_provider_config("embedding_main", configs)
    except Exception:
        embed_main_provider = {}

    try:
        embed_volc_provider = get_provider_config("embedding_volcengine", configs)
    except Exception:
        embed_volc_provider = {}

    local_fallback = os.environ.get("LOCAL_EMBED_MODEL", "bge-base").strip() or "bge-base"

    print(f"  config: project_root={PROJECT_ROOT}")
    print(f"  config: env_path={Path(env_path)}")
    print(
        f"  config: llm={llm_provider.get('provider', 'n.a.')} | {llm_provider.get('base_url', 'n.a.')} | {llm_provider.get('model', 'n.a.') or 'n.a.'}"
    )
    print(
        f"  config: embed_main={embed_main_provider.get('provider', 'n.a.')} | {embed_main_provider.get('base_url', 'n.a.')} | {embed_main_provider.get('model', 'n.a.') or 'n.a.'}"
    )
    print(
        f"  config: embed_volcengine={embed_volc_provider.get('provider', 'n.a.')} | {embed_volc_provider.get('base_url', 'n.a.')} | {embed_volc_provider.get('model', 'n.a.') or 'n.a.'}"
    )
    print(
        f"  config: embed_cascade=embedding_main -> embedding_volcengine -> local ({local_fallback})"
    )
    print()

    checks = [
        _check_dotenv(env_path),
        _test_llm(),
        _test_embedding(),
    ]

    all_ok = True
    for name, status in checks:
        if status.startswith("ERROR"):
            icon = "✗"
            all_ok = False
        elif status.startswith("WARN") or status.startswith("SKIP"):
            icon = "⚠"
        elif status.startswith("OK"):
            icon = "✓"
        else:
            icon = "?"
        print(f"  {icon} {name}: {status}")

    print()
    if all_ok:
        print("  ✓ All checks passed!")
    else:
        print("  ✗ Some checks failed — review above")

    return 0 if all_ok else 1


if __name__ == "__main__":
    # Direct invocation (for testing)
    parser = argparse.ArgumentParser(prog="paper-compass validate")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    args = parser.parse_args()
    sys.exit(execute_validate(args))
