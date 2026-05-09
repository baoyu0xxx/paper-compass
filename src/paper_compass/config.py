"""
Configuration loader for paper-compass.

Loads YAML config files and resolves environment variable references.
Designed as a thin, testable layer over the configs/ directory.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def _resolve_env(value: str) -> str:
    """Resolve ${ENV_VAR} or $ENV_VAR references in a string."""
    import re
    import os

    def replacer(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, "")

    return re.sub(r'\$\{(\w+)\}|\$(\w+)', replacer, value)


def _resolve_env_recursive(obj: Any) -> Any:
    """Recursively resolve env vars in dicts, lists, and strings."""
    if isinstance(obj, str):
        return _resolve_env(obj)
    elif isinstance(obj, dict):
        return {k: _resolve_env_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_recursive(v) for v in obj]
    return obj


def load_yaml_config(filepath: str, resolve_env: bool = True) -> Dict[str, Any]:
    """Load a single YAML config file.

    Args:
        filepath: Path to the YAML file.
        resolve_env: Whether to resolve ${ENV_VAR} references in values.

    Returns:
        Parsed config dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if resolve_env and data is not None:
        data = _resolve_env_recursive(data)

    return data if data is not None else {}


def load_all_configs(config_dir: str = "configs") -> Dict[str, Any]:
    """Load all YAML config files from a directory.

    Args:
        config_dir: Path to the config directory.

    Returns:
        Dictionary mapping config name (stem) to its parsed content.
    """
    dir_path = Path(config_dir)
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
    """Look up a specific provider config from the loaded providers.

    Args:
        provider_name: Name of the provider (key in providers.yaml).
        configs: Pre-loaded configs dict, or None to load fresh.

    Returns:
        Provider config dict with env vars resolved.

    Raises:
        KeyError: If provider_name is not found.
    """
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

    # Resolve env-var-referenced values
    for key in ["base_url_env", "model_env"]:
        if key in provider:
            env_name = provider.pop(key)
            target_field = {
                "base_url_env": "base_url",
                "model_env": "model",
            }[key]
            value = os.environ.get(env_name, "")
            if value:
            # If env var is empty/falsy, keep the existing default value
            # (provider.yaml's "model" field serves as the default)
                provider[target_field] = value

    # Resolve api_key_env
    if "api_key_env" in provider:
        env_name = provider.pop("api_key_env")
        value = os.environ.get(env_name, "")
        if value:
            # If env var is empty/falsy, keep the existing default value
            # (provider.yaml's "model" field serves as the default)
            provider["api_key"] = value

    return provider
