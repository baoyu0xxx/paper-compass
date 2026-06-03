"""Managed repo-local runtime helpers for paper-compass."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paper_compass.resources import project_root as detect_project_root

MIN_PYTHON = (3, 12)
VERSION_PROBE = "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
RUNTIME_METADATA = ".paper_compass_runtime.json"
BOOTSTRAP_HINT = "python scripts/bootstrap_runtime.py"
SKIP_RUNTIME_CHECK_ENV = "PAPER_COMPASS_SKIP_RUNTIME_CHECK"


class ManagedRuntimeError(RuntimeError):
    """Raised when the managed paper-compass runtime is missing or invalid."""


@dataclass(slots=True)
class RuntimeState:
    project_root: Path
    managed_venv: Path
    managed_python: Path
    metadata_path: Path
    current_python: Path
    current_python_version: str | None
    managed_exists: bool
    managed_active: bool
    status: str
    reasons: list[str]
    metadata: dict[str, Any]


def _resolve_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _normalize_path(path: Path) -> str:
    return os.path.normcase(str(_resolve_path(path)))


def resolve_project_root(root: str | Path | None = None) -> Path:
    if root is not None:
        return _resolve_path(Path(root))
    return _resolve_path(detect_project_root())


def managed_venv_dir(project_root: str | Path | None = None) -> Path:
    return project_root_path(project_root) / ".venv"


def project_root_path(project_root: str | Path | None = None) -> Path:
    return resolve_project_root(project_root)


def managed_python_path(project_root: str | Path | None = None) -> Path:
    root = project_root_path(project_root) / ".venv"
    windows = root / "Scripts" / "python.exe"
    posix = root / "bin" / "python"
    if windows.exists() or os.name == "nt":
        return windows
    return posix


def runtime_metadata_path(project_root: str | Path | None = None) -> Path:
    return managed_venv_dir(project_root) / RUNTIME_METADATA


def _read_metadata(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_metadata(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pyproject_meta(project_root: Path) -> tuple[str, str | None, str | None]:
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return ("unknown", None, None)
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = payload.get("project", {}) if isinstance(payload, dict) else {}
    version = str(project.get("version", "unknown"))
    requires_python = project.get("requires-python")
    return (version, str(requires_python) if requires_python else None, _sha256(pyproject))


def _lower_bound_from_requires_python(spec: str | None) -> tuple[int, int] | None:
    if not spec:
        return None
    for part in spec.split(","):
        part = part.strip()
        if part.startswith(">="):
            version = part[2:].strip().split(".")
            try:
                major = int(version[0])
                minor = int(version[1]) if len(version) > 1 else 0
                return (major, minor)
            except (ValueError, IndexError):
                return None
    return None


def _parse_version(version_text: str | None) -> tuple[int, int, int] | None:
    if not version_text:
        return None
    parts = version_text.strip().split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        return None
    return (major, minor, patch)


def _probe_python_version(python_executable: Path) -> str:
    try:
        result = subprocess.run(
            [str(python_executable), "-c", VERSION_PROBE],
            capture_output=True,
            text=True,
            cwd=str(python_executable.parent),
            check=False,
        )
    except OSError as exc:
        raise ManagedRuntimeError(f"failed to probe python version for {python_executable}: {exc}") from exc
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise ManagedRuntimeError(f"failed to probe python version for {python_executable}: {stderr}")
    version_text = result.stdout.strip()
    if not version_text:
        raise ManagedRuntimeError(f"failed to probe python version for {python_executable}: empty output")
    return version_text


def _minimum_python(project_root: Path) -> tuple[int, int]:
    _, requires_python, _ = _pyproject_meta(project_root)
    lower = _lower_bound_from_requires_python(requires_python)
    if lower is None:
        return MIN_PYTHON
    return max(MIN_PYTHON, lower)


def _ensure_python_supported(python_executable: Path, project_root: Path) -> str:
    version_text = _probe_python_version(python_executable)
    version_tuple = _parse_version(version_text)
    minimum = _minimum_python(project_root)
    if version_tuple is None or version_tuple[:2] < minimum:
        minimum_text = f"{minimum[0]}.{minimum[1]}"
        raise ManagedRuntimeError(
            f"paper-compass managed runtime requires Python >= {minimum_text}; "
            f"got {version_text} from {python_executable}"
        )
    return version_text


def _current_python_path(current_python: str | Path | None = None) -> Path:
    if current_python is not None:
        return _resolve_path(Path(current_python))
    return _resolve_path(Path(sys.executable))


def _install_target(with_dev: bool) -> str:
    return ".[dev]" if with_dev else "."


def _metadata_matches(metadata: dict[str, Any], project_root: Path, managed_python: Path, with_dev: bool) -> bool:
    if not metadata:
        return False
    project_version, _, pyproject_sha = _pyproject_meta(project_root)
    if metadata.get("project_version") != project_version:
        return False
    if metadata.get("pyproject_sha256") != pyproject_sha:
        return False
    if _normalize_path(Path(str(metadata.get("python_executable", managed_python)))) != _normalize_path(managed_python):
        return False
    extras = metadata.get("extras")
    if extras != (["dev"] if with_dev else []):
        return False
    return True


def runtime_state(
    project_root: str | Path | None = None,
    current_python: str | Path | None = None,
) -> RuntimeState:
    root = project_root_path(project_root)
    managed_venv = root / ".venv"
    managed_python = managed_python_path(root)
    metadata_path = runtime_metadata_path(root)
    metadata = _read_metadata(metadata_path)
    current = _current_python_path(current_python)

    reasons: list[str] = []
    status = "active"
    managed_exists = managed_python.exists()

    current_version = None
    if current.exists():
        try:
            current_version = _probe_python_version(current)
        except ManagedRuntimeError:
            current_version = None

    if not managed_exists:
        status = "missing"
        reasons.append(
            f"managed runtime not initialized at {managed_venv}; run {BOOTSTRAP_HINT}"
        )
    else:
        if not metadata:
            reasons.append(f"runtime metadata missing; run {BOOTSTRAP_HINT}")
            status = "stale"
        else:
            project_version, _, pyproject_sha = _pyproject_meta(root)
            if metadata.get("project_version") != project_version or metadata.get("pyproject_sha256") != pyproject_sha:
                reasons.append("managed runtime is out of date for the current project revision")
                status = "stale"
        if _normalize_path(current) != _normalize_path(managed_python):
            reasons.append("current interpreter does not match managed runtime")
            status = "inactive" if status == "active" else status

    managed_active = managed_exists and status == "active"
    return RuntimeState(
        project_root=root,
        managed_venv=managed_venv,
        managed_python=managed_python,
        metadata_path=metadata_path,
        current_python=current,
        current_python_version=current_version,
        managed_exists=managed_exists,
        managed_active=managed_active,
        status=status,
        reasons=reasons,
        metadata=metadata,
    )


def _runtime_error_message(state: RuntimeState, context: str) -> str:
    lines = [f"{context} runtime error"]
    if state.reasons:
        lines.extend(f"- {reason}" for reason in state.reasons)
    lines.append(f"- current python: {state.current_python}")
    lines.append(f"- managed python: {state.managed_python}")
    lines.append(f"- bootstrap: {BOOTSTRAP_HINT}")
    return "\n".join(lines)


def assert_managed_runtime_active(
    project_root: str | Path | None = None,
    current_python: str | Path | None = None,
    context: str = "paper-compass",
) -> RuntimeState:
    if os.environ.get(SKIP_RUNTIME_CHECK_ENV, "").strip().lower() in {"1", "true", "yes", "on"}:
        return runtime_state(project_root=project_root, current_python=current_python)

    state = runtime_state(project_root=project_root, current_python=current_python)
    if not state.managed_active:
        raise ManagedRuntimeError(_runtime_error_message(state, context))
    return state


def ensure_managed_runtime(
    project_root: str | Path | None = None,
    bootstrap_python: str | Path | None = None,
    with_dev: bool = True,
) -> RuntimeState:
    root = project_root_path(project_root)
    managed_venv = managed_venv_dir(root)
    managed_python = managed_python_path(root)
    metadata_path = runtime_metadata_path(root)

    bootstrap = _current_python_path(bootstrap_python)
    _ensure_python_supported(bootstrap, root)

    if not managed_python.exists():
        managed_venv.mkdir(parents=True, exist_ok=True)
        create_result = subprocess.run(
            [str(bootstrap), "-m", "venv", str(managed_venv)],
            capture_output=True,
            text=True,
            cwd=str(root),
            check=False,
        )
        if create_result.returncode != 0:
            stderr = create_result.stderr.strip() or create_result.stdout.strip() or "unknown error"
            raise ManagedRuntimeError(f"failed to create managed runtime: {stderr}")

    if not managed_python.exists():
        raise ManagedRuntimeError(f"managed runtime python not found after bootstrap: {managed_python}")

    _ensure_python_supported(managed_python, root)
    metadata = _read_metadata(metadata_path)
    if not _metadata_matches(metadata, root, managed_python, with_dev):
        install_target = _install_target(with_dev)
        install_result = subprocess.run(
            [str(managed_python), "-m", "pip", "install", "-e", install_target],
            capture_output=True,
            text=True,
            cwd=str(root),
            check=False,
        )
        if install_result.returncode != 0:
            stderr = install_result.stderr.strip() or install_result.stdout.strip() or "unknown error"
            raise ManagedRuntimeError(f"failed to install paper-compass into managed runtime: {stderr}")

    project_version, _, pyproject_sha = _pyproject_meta(root)
    managed_version = _probe_python_version(managed_python)
    payload = {
        "project_version": project_version,
        "pyproject_sha256": pyproject_sha,
        "python_executable": str(managed_python),
        "python_version": managed_version,
        "extras": ["dev"] if with_dev else [],
        "install_mode": "editable",
        "installed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    _write_metadata(metadata_path, payload)
    return runtime_state(project_root=root, current_python=managed_python)
