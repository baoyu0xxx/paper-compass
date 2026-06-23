from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SOURCE_CONFIG_FILENAME = "source_config.json"


def source_config_path(project_root: str | Path) -> Path:
    return Path(project_root) / "data" / "state" / SOURCE_CONFIG_FILENAME


def load_last_successful_zotero_source(path: str | Path) -> dict[str, str]:
    state_path = Path(path)
    if not state_path.exists():
        return {}

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}

    zotero = payload.get("zotero")
    if not isinstance(zotero, dict):
        return {}

    db_path = str(zotero.get("db_path", "") or "").strip()
    storage_path = str(zotero.get("storage_path", "") or "").strip()
    result: dict[str, str] = {}
    if db_path:
        result["zotero_sqlite_path"] = db_path
    if storage_path:
        result["zotero_storage_path"] = storage_path
    return result


def save_last_successful_zotero_source(
    path: str | Path,
    *,
    db_path: str,
    storage_path: str,
    source_kind: str,
    is_live_candidate: bool,
    last_success_at: str,
) -> None:
    state_path = Path(path)
    payload: dict[str, Any] = {
        "version": 1,
        "zotero": {
            "db_path": db_path,
            "storage_path": storage_path,
            "source_kind": source_kind,
            "is_live_candidate": bool(is_live_candidate),
            "last_success_at": last_success_at,
        },
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
