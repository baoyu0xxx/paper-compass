"""Load YAML configuration files from the repo or installed package resources."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def _resolve_env(value: str) -> str:
    """Resolve ${ENV_VAR} or $ENV_VAR references in a string."""
    import os
    import re

    def replacer(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, "")

    return re.sub(r"\$\{(\w+)\}|\$(\w+)", replacer, value)


def _resolve_env_recursive(obj: Any) -> Any:
    """Recursively resolve env vars in dicts, lists, and strings."""
    if isinstance(obj, str):
        return _resolve_env(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_recursive(v) for v in obj]
    return obj


def _candidate_paths(config_dir: str | Path) -> list[Path]:
    path = Path(config_dir)
    candidates: list[Path] = []

    if path.is_absolute():
        return [path]

    candidates.append(path)
    package_root = Path(__file__).resolve().parents[2]
    candidates.append(package_root / path)
    return candidates


def _resource_path(config_dir: str | Path) -> Path | None:
    path = Path(config_dir)
    if path.is_absolute():
        return None

    try:
        resource = files("paper_compass") / path.as_posix()
    except ModuleNotFoundError:
        return None

    try:
        if resource.is_dir():
            return Path(str(resource))
    except FileNotFoundError:
        return None
    return None


def resolve_config_dir(config_dir: str | Path = "configs") -> Path:
    """Resolve a config directory from cwd, repo root, or installed package data."""
    for candidate in _candidate_paths(config_dir):
        if candidate.exists() and candidate.is_dir():
            return candidate

    resource_dir = _resource_path(config_dir)
    if resource_dir is not None:
        return resource_dir

    return Path(config_dir)


def load_yaml_config(filepath: str, resolve_env: bool = True) -> Dict[str, Any]:
    """Load a single YAML config file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if resolve_env and data is not None:
        data = _resolve_env_recursive(data)

    return data if data is not None else {}


def load_all_configs(config_dir: str = "configs") -> Dict[str, Any]:
    """Load all YAML config files from a directory."""
    dir_path = resolve_config_dir(config_dir)
    configs: Dict[str, Any] = {}

    if not dir_path.exists():
        return configs

    for yaml_file in sorted(dir_path.glob("*.yaml")):
        stem = yaml_file.stem
        configs[stem] = load_yaml_config(str(yaml_file))

    return configs


def get_provider_config(
    provider_name: str, configs: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Look up a specific provider config from the loaded providers."""
    import os

    if configs is None:
        configs = load_all_configs()

    providers_cfg = configs.get("providers", {})
    providers = providers_cfg.get("providers", {})

    if provider_name not in providers:
        available = list(providers.keys())
        raise KeyError(
            f"Provider '{provider_name}' not found. Available: {available}"
        )

    provider = dict(providers[provider_name])

    env_field_map = {
        "base_url_env": "base_url",
        "model_env": "model",
        "api_key_env": "api_key",
    }
    for env_key, target_field in env_field_map.items():
        if env_key not in provider:
            continue
        env_name = provider.pop(env_key)
        value = _resolve_env_value(os.environ.get(env_name, ""))
        if value:
            provider[target_field] = value

    return provider


def _resolve_embedding_role_selection(
    configs: Dict[str, Any],
) -> tuple[str, str, list[str], Dict[str, Any], Dict[str, Any]]:
    providers_cfg = configs.get("providers", {})
    providers = providers_cfg.get("providers", {})
    roles = providers_cfg.get("roles", {})

    shared_provider = roles.get("embedding")
    pdf_provider = roles.get("pdf_embedding")
    wiki_provider = roles.get("wiki_embedding")
    legacy_fields = [
        name for name, value in (("pdf_embedding", pdf_provider), ("wiki_embedding", wiki_provider)) if value
    ]

    if pdf_provider and wiki_provider and pdf_provider != wiki_provider:
        raise ValueError(
            "pdf_embedding and wiki_embedding must reference the same embedding provider; split embedding roles are not supported"
        )

    if shared_provider:
        selected_provider = shared_provider
        config_source = "shared"
    else:
        selected_provider = pdf_provider or wiki_provider or "embedding_main"
        config_source = "legacy" if legacy_fields else "default"

    for legacy_name, legacy_value in (("pdf_embedding", pdf_provider), ("wiki_embedding", wiki_provider)):
        if shared_provider and legacy_value and legacy_value != selected_provider:
            raise ValueError(
                f"roles.embedding={selected_provider!r} conflicts with legacy roles.{legacy_name}={legacy_value!r}; use one shared embedding role"
            )

    return selected_provider, config_source, legacy_fields, providers, roles


def get_embedding_provider_order(configs: Optional[Dict[str, Any]] = None) -> list[str]:
    """Resolve embedding provider preference from one shared embedding role.

    Preferred config shape:
    - roles.embedding = <provider name>

    Legacy compatibility:
    - roles.pdf_embedding / roles.wiki_embedding may still exist temporarily
    - if both legacy keys exist, they must match

    Splitting paper/wiki embeddings is rejected because it would create
    incompatible embedding spaces between indexed papers and wiki vectors.
    """
    if configs is None:
        configs = load_all_configs()

    selected_provider, _config_source, _legacy_fields, providers, _roles = _resolve_embedding_role_selection(configs)

    ordered: list[str] = []
    for provider_name in (selected_provider, "embedding_main", "embedding_volcengine"):
        if provider_name in providers and provider_name not in ordered:
            ordered.append(provider_name)

    return ordered


def resolve_embedding_runtime(configs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve the shared embedding runtime used by paper and wiki indexing/search.

    Returns a normalized runtime description suitable for build/runtime logic,
    CLI status/validate output, and compatibility checks.
    """
    import os

    if configs is None:
        configs = load_all_configs()

    selected_provider, config_source, legacy_fields, _providers, _roles = _resolve_embedding_role_selection(configs)
    candidate_order = get_embedding_provider_order(configs)
    local_model = os.environ.get("LOCAL_EMBED_MODEL", "bge-base").strip() or "bge-base"

    configured_candidates: list[Dict[str, Any]] = []
    resolved_provider: str | None = None
    resolved_cloud_config: Dict[str, Any] | None = None

    for provider_name in candidate_order:
        provider_cfg = get_provider_config(provider_name, configs)
        candidate_info = {
            "name": provider_name,
            "provider": provider_cfg.get("provider", "openai"),
            "base_url": provider_cfg.get("base_url", ""),
            "model": provider_cfg.get("model", ""),
            "api_key": provider_cfg.get("api_key", ""),
            "api_key_configured": bool(provider_cfg.get("api_key", "")),
        }
        configured_candidates.append(candidate_info)
        if resolved_provider is None and provider_cfg.get("base_url") and provider_cfg.get("api_key"):
            resolved_provider = provider_name
            resolved_cloud_config = provider_cfg

    return {
        "role": "embedding",
        "config_source": config_source,
        "selected_provider": selected_provider,
        "resolved_provider": resolved_provider,
        "resolved_cloud_config": resolved_cloud_config,
        "candidate_order": candidate_order,
        "display_cascade": [*candidate_order, f"local ({local_model})"],
        "local_fallback_model": local_model,
        "legacy_fields": legacy_fields,
        "configured_candidates": configured_candidates,
    }


def _resolve_env_value(value: str) -> str:
    """Resolve a value that may be an $ENV_VAR reference."""
    import os

    if value.startswith("$"):
        inner_name = value[1:]
        resolved = os.environ.get(inner_name, "")
        if resolved:
            return resolved
        return value
    return value
