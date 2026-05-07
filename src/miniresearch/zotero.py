"""
Zotero sync layer for paper-compass.

Reads PDFs from a fixed root directory, optionally merges external metadata
(CSV/JSON), and outputs manifest.csv + library.json.

Design:
  - Level 1: directory scan only (always works)
  - Level 2: directory scan + external metadata file merge
  - Level 3: directory scan + sqlite (deferred to later phase)
"""

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── helpers ───────────────────────────────────────────────────────────────────

def _normalize_filename(name: str) -> str:
    """Normalize a filename for fuzzy matching: lowercase, strip ext, collapse punctuation."""
    name = name.lower()
    # strip extension
    if "." in name:
        name = name.rsplit(".", 1)[0]
    # replace common separators with space
    for ch in "_-.,;:()[]{}":
        name = name.replace(ch, " ")
    # collapse whitespace
    return " ".join(name.split())


def _compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _generate_doc_id(relative_path: str, sha256: Optional[str] = None) -> str:
    """Generate a stable doc_id from relative_path (and optionally sha256)."""
    if sha256:
        return hashlib.sha256(f"{relative_path}:{sha256}".encode()).hexdigest()[:12]
    return hashlib.sha256(relative_path.encode()).hexdigest()[:12]


# ── PDF scanning ─────────────────────────────────────────────────────────────

def scan_pdf_root(pdf_root: str) -> List[Path]:
    """Recursively find all PDF files under pdf_root.

    Returns a list of Path objects, excluding zero-size files.
    """
    root = Path(pdf_root)
    if not root.exists():
        raise FileNotFoundError(f"PDF root directory not found: {pdf_root}")

    pdfs = []
    for pdf_path in root.rglob("*.pdf"):
        try:
            if pdf_path.stat().st_size > 0:
                pdfs.append(pdf_path)
        except OSError:
            continue

    return sorted(pdfs)


def build_base_record(pdf_path: Path, pdf_root: str) -> Dict[str, Any]:
    """Build a base record from a scanned PDF path.

    Fields: pdf_path, relative_path, file_name, file_size, modified_at.
    """
    root = Path(pdf_root)
    stat = pdf_path.stat()
    return {
        "pdf_path": str(pdf_path),
        "relative_path": str(pdf_path.relative_to(root)),
        "file_name": pdf_path.name,
        "file_size": stat.st_size,
        "modified_at": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
    }


# ── metadata loading ─────────────────────────────────────────────────────────

def load_external_metadata(
    metadata_path: str,
) -> List[Dict[str, Any]]:
    """Load external metadata from a CSV or JSON file.

    CSV must have a header row. JSON must be a list of record dicts.

    Returns a list of metadata records.
    """
    path = Path(metadata_path)
    if not path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    suffix = path.suffix.lower()

    if suffix == ".csv":
        records = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(dict(row))
        return records

    elif suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        # single object
        if isinstance(data, dict):
            return [data]
        raise ValueError(f"JSON metadata must be a list or dict, got {type(data)}")

    else:
        raise ValueError(f"Unsupported metadata format: {suffix}. Use .csv or .json")


# ── merging ───────────────────────────────────────────────────────────────────

def merge_records(
    base_records: List[Dict[str, Any]],
    metadata_records: Optional[List[Dict[str, Any]]] = None,
    compute_sha: bool = True,
) -> List[Dict[str, Any]]:
    """Merge scanned PDF records with external metadata.

    Matching priority:
      1. relative_path exact match
      2. file_name exact match
      3. normalized file_name fuzzy match

    Returns enriched records with metadata_source markers.
    """
    if metadata_records is None:
        metadata_records = []

    # Build lookup indices for metadata
    meta_by_relpath: Dict[str, Dict[str, Any]] = {}
    meta_by_filename: Dict[str, List[Dict[str, Any]]] = {}
    meta_by_normname: Dict[str, List[Dict[str, Any]]] = {}

    for meta in metadata_records:
        rel = meta.get("relative_path") or meta.get("file_location") or ""
        fname = meta.get("file_name") or os.path.basename(rel) or ""
        norm = _normalize_filename(fname)

        if rel:
            # Use basename of relative_path as key for matching scanned records
            meta_by_relpath[rel] = meta
        if fname:
            meta_by_filename.setdefault(fname, []).append(meta)
        if norm:
            meta_by_normname.setdefault(norm, []).append(meta)

    enriched: List[Dict[str, Any]] = []

    for rec in base_records:
        meta = None
        match_method = "scan_only"

        # Priority 1: relative_path
        if rec["relative_path"] in meta_by_relpath:
            meta = meta_by_relpath[rec["relative_path"]]
            match_method = "external_csv"

        # Priority 2: file_name
        elif rec["file_name"] in meta_by_filename:
            candidates = meta_by_filename[rec["file_name"]]
            meta = candidates[0]
            match_method = "external_csv"

        # Priority 3: normalized file_name
        else:
            norm_name = _normalize_filename(rec["file_name"])
            if norm_name in meta_by_normname:
                candidates = meta_by_normname[norm_name]
                meta = candidates[0]
                match_method = "external_csv"

        # Merge
        merged = dict(rec)  # base record
        merged["metadata_source"] = match_method

        if meta:
            merged["title"] = (
                meta.get("title")
                or meta.get("Title")
                or rec["file_name"].rsplit(".", 1)[0]
            )
            merged["doi"] = meta.get("doi") or meta.get("DOI") or ""
            merged["journal"] = meta.get("journal") or meta.get("Journal") or ""
            merged["year"] = _parse_year(meta.get("year") or meta.get("Year") or "")
            merged["authors"] = _parse_authors(meta)
            merged["collections"] = _parse_list_field(meta, "collections")
            merged["tags"] = _parse_list_field(meta, "tags")

            # Keep matched metadata file_name if different
            if not merged.get("file_name"):
                merged["file_name"] = rec["file_name"]
        else:
            merged["title"] = rec["file_name"].rsplit(".", 1)[0]
            merged["doi"] = ""
            merged["journal"] = ""
            merged["year"] = None
            merged["authors"] = []
            merged["collections"] = []
            merged["tags"] = []

        # Compute sha256 and doc_id
        if compute_sha:
            try:
                merged["sha256"] = _compute_sha256(rec["pdf_path"])
            except OSError:
                merged["sha256"] = ""
        else:
            merged["sha256"] = ""

        merged["doc_id"] = _generate_doc_id(
            rec["relative_path"], merged.get("sha256")
        )

        enriched.append(merged)

    return enriched


def _parse_year(value: Any) -> Optional[int]:
    """Parse year from various input formats."""
    if value is None:
        return None
    try:
        return int(str(value).strip()[:4])
    except (ValueError, TypeError):
        return None


def _parse_authors(meta: Dict[str, Any]) -> List[str]:
    """Parse authors from metadata record (supports both list and delimiter-separated string)."""
    authors = meta.get("authors") or meta.get("Authors") or meta.get("creators") or ""
    if isinstance(authors, list):
        return [str(a).strip() for a in authors if str(a).strip()]
    if isinstance(authors, str) and authors.strip():
        # Try multiple delimiters
        for sep in ["; ", ";", ", ", ","]:
            if sep in authors:
                return [a.strip() for a in authors.split(sep) if a.strip()]
        return [authors.strip()]
    return []


def _parse_list_field(meta: Dict[str, Any], field: str) -> List[str]:
    """Parse collections/tags from metadata (supports list or delimiter-separated)."""
    value = meta.get(field) or meta.get(field.capitalize()) or ""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        for sep in ["; ", ";"]:
            if sep in value:
                return [v.strip() for v in value.split(sep) if v.strip()]
        return [value.strip()]
    return []


# ── output ────────────────────────────────────────────────────────────────────

def build_manifest_rows(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Convert enriched records to manifest CSV rows."""
    rows = []
    for rec in records:
        rows.append(
            {
                "file_location": rec.get("relative_path", ""),
                "title": rec.get("title", ""),
                "doi": rec.get("doi", ""),
                "authors": ";".join(rec.get("authors", [])),
                "year": str(rec.get("year") or ""),
                "journal": rec.get("journal", ""),
                "collections": ";".join(rec.get("collections", [])),
                "tags": ";".join(rec.get("tags", [])),
            }
        )
    return rows


def write_manifest_csv(
    records: List[Dict[str, Any]],
    output_path: str,
) -> int:
    """Write manifest.csv for PaperQA consumption.

    Returns the number of records written.
    """
    rows = build_manifest_rows(records)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "file_location",
                "title",
                "doi",
                "authors",
                "year",
                "journal",
                "collections",
                "tags",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def write_library_json(
    records: List[Dict[str, Any]],
    output_path: str,
) -> int:
    """Write library.json for wiki/MCP consumption.

    Returns the number of records written.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Select only the agreed-upon fields
    slim = []
    for rec in records:
        slim.append(
            {
                "doc_id": rec.get("doc_id", ""),
                "title": rec.get("title", ""),
                "pdf_path": rec.get("pdf_path", ""),
                "relative_path": rec.get("relative_path", ""),
                "file_name": rec.get("file_name", ""),
                "file_size": rec.get("file_size", 0),
                "modified_at": rec.get("modified_at", ""),
                "sha256": rec.get("sha256", ""),
                "doi": rec.get("doi", ""),
                "authors": rec.get("authors", []),
                "year": rec.get("year"),
                "journal": rec.get("journal", ""),
                "collections": rec.get("collections", []),
                "tags": rec.get("tags", []),
                "metadata_source": rec.get("metadata_source", "scan_only"),
            }
        )

    with open(out, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=2)

    return len(slim)


# ── sync report ──────────────────────────────────────────────────────────────

def generate_sync_report(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a summary report of the sync operation."""
    total = len(records)
    with_meta = sum(
        1 for r in records if r.get("metadata_source") != "scan_only"
    )
    missing_title = sum(1 for r in records if not r.get("title"))
    missing_doi = sum(1 for r in records if not r.get("doi"))
    missing_authors = sum(1 for r in records if not r.get("authors"))

    # Detect duplicate file_names
    fnames = [r.get("file_name", "") for r in records]
    duplicates = len(fnames) - len(set(fnames))

    return {
        "total_pdfs": total,
        "with_metadata": with_meta,
        "scan_only": total - with_meta,
        "missing_title": missing_title,
        "missing_doi": missing_doi,
        "missing_authors": missing_authors,
        "duplicate_filenames": duplicates,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
