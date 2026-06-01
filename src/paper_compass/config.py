"""Load YAML configuration files from the repo or installed package resources."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

@dataclass(frozen=True)
class PathSettings:
    library_json_path: str = "data/zotero-export/library.json"
    text_dir: str = "data/texts"
    wiki_root: str = "wiki"
    vectordb_path: str = "data/vectordb"
    zotero_sqlite_path: str = ""
    zotero_storage_path: str = ""


@dataclass(frozen=True)
class IndexingSettings:
    large_incremental_change_ratio: float = 0.30
    large_incremental_change_minimum: int = 3
    require_dry_run_for_large_incremental: bool = True


PATH_SETTINGS_ENV_MAP = {
    "library_json_path": "PAPER_COMPASS_LIBRARY_PATH",
    "text_dir": "PAPER_COMPASS_TEXT_DIR",
    "wiki_root": "PAPER_COMPASS_WIKI_ROOT",
    "vectordb_path": "PAPER_COMPASS_VECTORDB_PATH",
    "zotero_sqlite_path": "ZOTERO_SQLITE_PATH",
    "zotero_storage_path": "ZOTERO_STORAGE_PATH",
}


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


def _nonempty(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def resolve_path_settings(
    configs: Optional[Dict[str, Any]] = None,
    *,
    overrides: Optional[Dict[str, str | None]] = None,
) -> PathSettings:
    """Resolve common user paths with CLI > environment > YAML > safe defaults precedence."""
    import os

    if configs is None:
        configs = load_all_configs()
    overrides = overrides or {}
    yaml_paths = configs.get("paths", {}).get("paths", {})
    defaults = PathSettings()
    resolved: dict[str, str] = {}

    for field_name, env_name in PATH_SETTINGS_ENV_MAP.items():
        cli_value = _nonempty(overrides.get(field_name))
        env_value = _nonempty(os.environ.get(env_name))
        config_value = _nonempty(yaml_paths.get(field_name))
        default_value = getattr(defaults, field_name)
        resolved[field_name] = cli_value or env_value or config_value or default_value

    return PathSettings(**resolved)


def resolve_indexing_settings(configs: Optional[Dict[str, Any]] = None) -> IndexingSettings:
    """Resolve indexing safety thresholds from rag.indexing with safe defaults."""
    if configs is None:
        configs = load_all_configs()
    indexing = configs.get("rag", {}).get("rag", {}).get("indexing", {})
    defaults = IndexingSettings()
    return IndexingSettings(
        large_incremental_change_ratio=float(
            indexing.get("large_incremental_change_ratio", defaults.large_incremental_change_ratio)
        ),
        large_incremental_change_minimum=int(
            indexing.get("large_incremental_change_minimum", defaults.large_incremental_change_minimum)
        ),
        require_dry_run_for_large_incremental=bool(
            indexing.get("require_dry_run_for_large_incremental", defaults.require_dry_run_for_large_incremental)
        ),
    )


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

    if legacy_fields:
        raise ValueError(
            "roles.pdf_embedding / roles.wiki_embedding are no longer supported; "
            "use one shared roles.embedding so papers and wiki stay in the same embedding space"
        )

    selected_provider = shared_provider or "embedding_main"
    config_source = "shared" if shared_provider else "default"

    return selected_provider, config_source, legacy_fields, providers, roles


def get_embedding_provider_order(configs: Optional[Dict[str, Any]] = None) -> list[str]:
    """Resolve embedding provider preference from one shared embedding role.

    Preferred config shape:
    - roles.embedding = <provider name>

    Legacy split roles (`roles.pdf_embedding` / `roles.wiki_embedding`) are rejected
    because they can create incompatible paper and wiki embedding spaces.

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
