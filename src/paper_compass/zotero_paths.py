from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


DEFAULT_BACKUP_ROOTS: list[Path] = []


@dataclass(frozen=True)
class ZoteroPathAttempt:
    path: str
    reason: str


@dataclass(frozen=True)
class ZoteroSourceResolution:
    db_path: Path
    storage_path: Path
    source_kind: str
    tried: List[ZoteroPathAttempt]
    is_live_candidate: bool = False


class ZoteroSourceNotFoundError(FileNotFoundError):
    def __init__(self, tried: Sequence[ZoteroPathAttempt]):
        self.tried = list(tried)
        bullet_list = "\n".join(f"- {attempt.path}: {attempt.reason}" for attempt in self.tried)
        message = (
            "Could not locate a usable Zotero database + storage directory pair.\n"
            "Tried candidates:\n"
            f"{bullet_list}\n"
            "You can override auto-discovery with --db-path /path/to/zotero.sqlite "
            "and optionally --storage-path /path/to/storage."
        )
        super().__init__(message)


def _dedupe_paths(paths: Iterable[Path]) -> List[Path]:
    seen: set[str] = set()
    result: List[Path] = []
    for path in paths:
        normalized = str(path.expanduser())
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(Path(normalized))
    return result


def _candidate_db_paths(root: Path) -> List[Path]:
    return [root / "zotero.sqlite"]


def _looks_like_live_zotero_sqlite(db_candidate: Path) -> bool:
    return db_candidate.name.lower() == "zotero.sqlite"


def _default_root_candidates() -> List[Path]:
    candidates: List[Path] = [Path("~/Zotero").expanduser()]

    userprofile = os.environ.get("USERPROFILE", "").strip()
    if userprofile:
        candidates.append(Path(userprofile) / "Zotero")

    for windows_users_root in (Path("/c/Users"), Path("/mnt/c/Users")):
        if windows_users_root.exists():
            for user_dir in sorted(p for p in windows_users_root.iterdir() if p.is_dir()):
                candidates.append(user_dir / "Zotero")
                roaming_profiles = user_dir / "AppData" / "Roaming" / "Zotero" / "Zotero" / "Profiles"
                if roaming_profiles.exists():
                    for profile_dir in sorted(p for p in roaming_profiles.iterdir() if p.is_dir()):
                        candidates.append(profile_dir)

    return _dedupe_paths(candidates)


def _backup_root_candidates(extra_roots: Optional[Sequence[Path]] = None) -> List[Path]:
    combined = list(DEFAULT_BACKUP_ROOTS)
    env_backup_root = os.environ.get("ZOTERO_BACKUP_ROOT", "").strip()
    if env_backup_root:
        combined.append(Path(env_backup_root))
    if extra_roots:
        combined.extend(Path(p) for p in extra_roots)
    return _dedupe_paths(combined)


def _resolve_candidate(
    db_candidate: Path,
    *,
    storage_override: Optional[Path],
    source_kind: str,
    tried: List[ZoteroPathAttempt],
    is_live_candidate: bool,
) -> Optional[ZoteroSourceResolution]:
    db_candidate = db_candidate.expanduser()
    if not db_candidate.exists():
        tried.append(ZoteroPathAttempt(path=str(db_candidate), reason="database file not found"))
        return None

    if not db_candidate.is_file():
        tried.append(ZoteroPathAttempt(path=str(db_candidate), reason="database path exists but is not a file"))
        return None

    try:
        if db_candidate.stat().st_size <= 0:
            tried.append(ZoteroPathAttempt(path=str(db_candidate), reason="database file is empty"))
            return None
    except OSError as exc:
        tried.append(ZoteroPathAttempt(path=str(db_candidate), reason=f"unable to stat database file: {exc}"))
        return None

    storage_path = storage_override.expanduser() if storage_override else db_candidate.parent / "storage"
    if not storage_path.exists() or not storage_path.is_dir():
        tried.append(
            ZoteroPathAttempt(
                path=str(db_candidate),
                reason=f"storage directory not found: {storage_path}",
            )
        )
        return None

    return ZoteroSourceResolution(
        db_path=db_candidate,
        storage_path=storage_path,
        source_kind=source_kind,
        tried=list(tried),
        is_live_candidate=is_live_candidate,
    )


def resolve_zotero_source(
    db_path: Optional[str] = None,
    storage_path: Optional[str] = None,
    *,
    default_roots: Optional[Sequence[Path]] = None,
    backup_roots: Optional[Sequence[Path]] = None,
    env: Optional[dict[str, str]] = None,
) -> ZoteroSourceResolution:
    env_map = env if env is not None else os.environ
    tried: List[ZoteroPathAttempt] = []
    storage_override = Path(storage_path).expanduser() if storage_path else None
    if storage_override is None:
        env_storage_path = env_map.get("ZOTERO_STORAGE_PATH", "").strip()
        if env_storage_path:
            storage_override = Path(env_storage_path).expanduser()

    explicit_db_path = db_path or None
    if explicit_db_path:
        resolved = _resolve_candidate(
            Path(explicit_db_path),
            storage_override=storage_override,
            source_kind="explicit",
            tried=tried,
            is_live_candidate=_looks_like_live_zotero_sqlite(Path(explicit_db_path)),
        )
        if resolved is not None:
            return resolved
        raise ZoteroSourceNotFoundError(tried)

    env_db_path = env_map.get("ZOTERO_SQLITE_PATH", "").strip()
    if env_db_path:
        resolved = _resolve_candidate(
            Path(env_db_path),
            storage_override=storage_override,
            source_kind="env",
            tried=tried,
            is_live_candidate=_looks_like_live_zotero_sqlite(Path(env_db_path)),
        )
        if resolved is not None:
            return resolved

    default_roots = list(default_roots) if default_roots is not None else _default_root_candidates()
    for root in default_roots:
        for candidate in _candidate_db_paths(Path(root)):
            resolved = _resolve_candidate(
                candidate,
                storage_override=storage_override,
                source_kind="default",
                tried=tried,
                is_live_candidate=True,
            )
            if resolved is not None:
                return resolved

    backup_roots = list(backup_roots) if backup_roots is not None else _backup_root_candidates()
    for root in backup_roots:
        for candidate in _candidate_db_paths(Path(root)):
            resolved = _resolve_candidate(
                candidate,
                storage_override=storage_override,
                source_kind="backup",
                tried=tried,
                is_live_candidate=False,
            )
            if resolved is not None:
                return resolved

    raise ZoteroSourceNotFoundError(tried)
