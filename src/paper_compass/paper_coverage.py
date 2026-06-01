"""Local paper coverage diagnosis utilities.

These helpers answer a single question: for a given paper title or Zotero key,
which local layer currently covers it (library.json, texts, vectordb, wiki)?
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CoverageLayerStatus:
    found: bool = False
    path: str = ""
    exists: bool = False
    size: int = 0
    note: str = ""


@dataclass
class PaperCoverageReport:
    query: str
    query_norm: str
    library_match: Dict[str, Any] = field(default_factory=dict)
    text_file: CoverageLayerStatus = field(default_factory=CoverageLayerStatus)
    pdf_file: CoverageLayerStatus = field(default_factory=CoverageLayerStatus)
    vector_index: Dict[str, Any] = field(default_factory=dict)
    wiki_page: CoverageLayerStatus = field(default_factory=CoverageLayerStatus)
    diagnosis: str = "unknown"
    recommendations: List[str] = field(default_factory=list)


def _normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _safe_load_library(library_path: str) -> list[dict[str, Any]]:
    path = Path(library_path)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _find_library_match(query: str, library_path: str) -> dict[str, Any]:
    records = _safe_load_library(library_path)
    if not records:
        return {"found": False, "key": None, "title": None, "reason": "library_missing_or_empty"}

    q = query.strip().lower()
    q_norm = _normalize_text(query)
    exact_title_matches: list[dict[str, Any]] = []
    fuzzy_matches: list[dict[str, Any]] = []

    for rec in records:
        key = str(rec.get("key", "") or "")
        title = str(rec.get("title", "") or "")
        title_norm = _normalize_text(title)
        doi = str(rec.get("doi", "") or "").strip().lower()

        if q and (q == key.lower() or q == doi or q == title.lower()):
            exact_title_matches.append(rec)
            continue
        if q_norm and q_norm == title_norm:
            exact_title_matches.append(rec)
            continue
        if q_norm and q_norm in title_norm:
            fuzzy_matches.append(rec)

    chosen: Optional[dict[str, Any]] = None
    reason = "title_not_found_in_library"
    if exact_title_matches:
        chosen = exact_title_matches[0]
        reason = "exact_title_or_key_match"
    elif fuzzy_matches:
        chosen = fuzzy_matches[0]
        reason = "fuzzy_title_match"

    if chosen is None:
        return {"found": False, "key": None, "title": None, "reason": reason}

    return {
        "found": True,
        "key": chosen.get("key"),
        "title": chosen.get("title"),
        "year": chosen.get("year"),
        "collections": chosen.get("collections", []),
        "tags": chosen.get("tags", []),
        "reason": reason,
    }


def _load_manifest_item(manifest_path: Path, key: str) -> Optional[dict[str, Any]]:
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    items = payload.get("items", {}) or {}
    item = items.get(key)
    return item if isinstance(item, dict) else None


def _pick_manifest_path(db_path: Path) -> Path:
    candidates = sorted(db_path.glob("*.manifest.json"))
    if not candidates:
        return db_path / "papers.manifest.json"
    for candidate in candidates:
        if candidate.name.startswith("papers_"):
            return candidate
    return candidates[0]


def inspect_paper_coverage(
    query: str,
    *,
    library_path: str = "data/zotero-export/library.json",
    text_dir: str = "data/texts",
    db_path: str = "data/vectordb",
    wiki_root: str = "wiki",
) -> PaperCoverageReport:
    library_match = _find_library_match(query, library_path)
    report = PaperCoverageReport(query=query, query_norm=_normalize_text(query), library_match=library_match)

    key = library_match.get("key")
    if not key:
        report.diagnosis = "missing_from_library_json"
        report.recommendations = [
            "先检查 Zotero 导出是否刷新到 data/zotero-export/library.json",
            "如果 Zotero 已有但本地没有，先跑 sync_zotero 再做增量索引",
        ]
        return report

    text_path = Path(text_dir) / f"{key}.txt"
    report.text_file = CoverageLayerStatus(
        found=text_path.exists() and text_path.is_file(),
        path=str(text_path),
        exists=text_path.exists(),
        size=text_path.stat().st_size if text_path.exists() and text_path.is_file() else 0,
        note="text_file_for_library_key",
    )

    pdf_path = ""
    for rec in _safe_load_library(library_path):
        if rec.get("key") == key:
            pdf_path = str(rec.get("pdf_path", "") or "")
            break
    pdf_file = Path(pdf_path) if pdf_path else None
    report.pdf_file = CoverageLayerStatus(
        found=bool(pdf_file and pdf_file.exists()),
        path=str(pdf_file) if pdf_file else "",
        exists=bool(pdf_file and pdf_file.exists()),
        size=pdf_file.stat().st_size if pdf_file and pdf_file.exists() else 0,
        note="pdf_path_from_library_json",
    )

    manifest_path = _pick_manifest_path(Path(db_path))
    item = _load_manifest_item(manifest_path, key)
    report.vector_index = {
        "found": item is not None,
        "manifest_path": str(manifest_path),
        "chunk_count": item.get("chunk_count") if item else 0,
        "text_sha1": item.get("text_sha1") if item else "",
        "embedding_model_id": item.get("embedding_model_id") if item else "",
    }

    wiki_file = Path(wiki_root) / "papers" / f"{key}.md"
    report.wiki_page = CoverageLayerStatus(
        found=wiki_file.exists() and wiki_file.is_file(),
        path=str(wiki_file),
        exists=wiki_file.exists(),
        size=wiki_file.stat().st_size if wiki_file.exists() and wiki_file.is_file() else 0,
        note="wiki_page_by_key",
    )

    if not report.text_file.found and not report.pdf_file.found:
        report.diagnosis = "library_entry_without_text_or_pdf"
        report.recommendations = [
            "检查该条目是否有 pdf_path/text_file",
            "确认 sync_zotero 是否成功抽取文本或绑定 PDF",
        ]
    elif not report.vector_index.get("found"):
        report.diagnosis = "library_text_present_but_missing_from_vectordb"
        report.recommendations = [
            "检查 build_index.py 增量索引是否跳过了该条目",
            "查看 manifest / vectordb 一致性，并重新执行安全增量索引",
        ]
    else:
        report.diagnosis = "covered"
        report.recommendations = [
            "若检索仍命中不到，进一步检查 search_library / search_passages 排序与阈值",
        ]

    return report
