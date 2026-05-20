"""Resolve package-resident resource paths for configs and prompts."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _resource_root() -> Path | None:
    try:
        root = files("paper_compass")
    except ModuleNotFoundError:
        return None

    try:
        return Path(str(root))
    except FileNotFoundError:
        return None


def package_root() -> Path:
    resource_root = _resource_root()
    if resource_root is not None:
        return resource_root
    return PACKAGE_ROOT


def project_root() -> Path:
    root = package_root()
    if root.name == "paper_compass":
        return root.parent.parent
    if root.name == "src":
        return root.parent
    return root


def resolve_package_path(relative_path: str | Path) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        return path

    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate

    package_candidate = package_root() / path
    if package_candidate.exists():
        return package_candidate

    repo_candidate = project_root() / path
    if repo_candidate.exists():
        return repo_candidate

    return cwd_candidate
