"""
Wiki writeback store for paper-compass.

Handles writing generated wiki pages to the filesystem with frontmatter
and updating index.md / log.md.
"""

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Thread-safe guards for index.md and log.md (multiple workers
# may call save_query_to_wiki() concurrently).
_index_lock = threading.Lock()
_log_lock = threading.Lock()


def _slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:80]


def _extract_item_key(source_refs: List[str]) -> str:
    for ref in source_refs:
        match = re.match(r"zotero:([A-Za-z0-9]+)$", ref or "")
        if match:
            return match.group(1).upper()
    return ""


def _generate_filename(title: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(title)
    return f"{date_str}-{slug}.md"


def _generate_unique_filename(title: str, item_key: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(title)
    suffix = f"-{item_key.lower()}" if item_key else ""
    return f"{date_str}-{slug}{suffix}.md"


def _filename_tail(md_path: Path) -> str:
    match = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)$", md_path.stem)
    return match.group(1) if match else md_path.stem


def _find_same_slug_paths(type_dir: Path, slug: str) -> List[Path]:
    matched: List[Path] = []
    for md_file in sorted(type_dir.glob("*.md")):
        tail = _filename_tail(md_file)
        if tail == slug or tail.startswith(f"{slug}-"):
            matched.append(md_file)
    return matched


def _path_has_item_key(md_path: Path, item_key: str) -> bool:
    if not item_key or not md_path.exists():
        return False
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return False
    return bool(re.search(rf"zotero:{re.escape(item_key)}\b", text, flags=re.IGNORECASE))


def _format_frontmatter(fields: Dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
        elif isinstance(value, str) and "\n" in value:
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def plan_save_query_to_wiki(
    title: str,
    content: str,
    target_type: str = "queries",
    source_refs: Optional[List[str]] = None,
    confidence: str = "medium",
    tags: Optional[List[str]] = None,
    wiki_root: str = "./wiki",
) -> Dict[str, Any]:
    root = Path(wiki_root)
    type_dir = root / target_type
    if source_refs is None:
        source_refs = []
    if tags is None:
        tags = []

    slug = _slugify(title)
    item_key = _extract_item_key(source_refs)
    filename = _generate_filename(title)
    page_path = type_dir / filename
    existing_same_slug = _find_same_slug_paths(type_dir, slug)
    same_key_path = next((path for path in existing_same_slug if _path_has_item_key(path, item_key)), None)
    linked_pages = [ref for ref in source_refs if ref.startswith("wiki/")]

    return {
        "title": title,
        "content": content,
        "target_type": target_type,
        "source_refs": source_refs,
        "confidence": confidence,
        "tags": tags,
        "wiki_root": str(root),
        "page_path": str(page_path),
        "filename": filename,
        "slug": slug,
        "item_key": item_key,
        "would_write": True,
        "conflict": bool(existing_same_slug),
        "conflict_paths": [str(path) for path in existing_same_slug],
        "same_key_path": str(same_key_path) if same_key_path else "",
        "linked_pages": linked_pages,
        "index_update_preview": (root / "index.md").exists(),
        "log_update_preview": True,
    }


def commit_save_query_to_wiki(plan: Dict[str, Any], upsert_mode: str = "create") -> Dict[str, Any]:
    root = Path(plan["wiki_root"])
    type_dir = root / plan["target_type"]
    type_dir.mkdir(parents=True, exist_ok=True)

    conflict_paths = [Path(path) for path in plan.get("conflict_paths", [])]
    same_key_path = Path(plan["same_key_path"]) if plan.get("same_key_path") else None
    if conflict_paths and upsert_mode == "create":
        raise ValueError(
            f"Wiki page slug conflict for '{plan['slug']}'. Existing paths: {', '.join(str(p) for p in conflict_paths)}"
        )

    page_path = Path(plan["page_path"])
    if conflict_paths and upsert_mode == "replace_if_same_slug":
        page_path = conflict_paths[0]
    elif upsert_mode == "replace_if_same_key" and same_key_path is not None:
        page_path = same_key_path
    elif conflict_paths and upsert_mode == "create_unique":
        page_path = type_dir / _generate_unique_filename(plan["title"], plan.get("item_key", ""))

    now = datetime.now(timezone.utc).isoformat()
    frontmatter_fields = {
        "title": plan["title"],
        "created": now,
        "updated": now,
        "type": plan["target_type"],
        "tags": plan["tags"],
        "sources": plan["source_refs"],
        "confidence": plan["confidence"],
    }
    other_conflicts = [str(path) for path in conflict_paths if path != page_path]
    if other_conflicts:
        frontmatter_fields["duplicate_slug"] = True
        frontmatter_fields["conflict_paths"] = other_conflicts
    frontmatter = _format_frontmatter(frontmatter_fields)

    full_content = f"{frontmatter}\n\n# {plan['title']}\n\n{plan['content']}\n"
    page_path.write_text(full_content, encoding="utf-8")

    with _index_lock:
        index_updated = _update_index(root / "index.md", plan["title"], plan["target_type"], page_path.name)
    with _log_lock:
        log_updated = _update_log(root / "log.md", plan["title"], plan["target_type"], str(page_path))

    return {
        "page_path": str(page_path),
        "created": True,
        "linked_pages": plan["linked_pages"],
        "log_updated": log_updated,
        "index_updated": index_updated,
        "conflict": bool(conflict_paths),
        "slug": plan["slug"],
    }


def save_query_to_wiki(
    title: str,
    content: str,
    target_type: str = "queries",
    source_refs: Optional[List[str]] = None,
    confidence: str = "medium",
    tags: Optional[List[str]] = None,
    wiki_root: str = "./wiki",
    upsert_mode: str = "create",
) -> Dict[str, Any]:
    """Save a wiki page to the filesystem with frontmatter and index/log update."""
    plan = plan_save_query_to_wiki(
        title=title,
        content=content,
        target_type=target_type,
        source_refs=source_refs,
        confidence=confidence,
        tags=tags,
        wiki_root=wiki_root,
    )
    return commit_save_query_to_wiki(plan, upsert_mode=upsert_mode)


def _update_index(index_path: Path, title: str, page_type: str, filename: str) -> bool:
    if not index_path.exists():
        return False
    try:
        content = index_path.read_text(encoding="utf-8")
    except Exception:
        return False

    for section_name in [page_type.capitalize(), page_type]:
        pattern = re.compile(rf"^##\s+{re.escape(section_name)}\s*$", re.MULTILINE | re.IGNORECASE)
        match = pattern.search(content)
        if match:
            insert_pos = match.end()
            link = f"[{title}]({page_type}/{filename})"
            if link not in content:
                new_content = content[:insert_pos] + f"\n- {link}" + content[insert_pos:]
                index_path.write_text(new_content, encoding="utf-8")
                return True
            return False
    return False


def _update_log(log_path: Path, title: str, page_type: str, page_path_str: str) -> bool:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    entry = f"\n## [{date_str}] writeback | {page_type}\n- Page: [{title}]({page_path_str})\n- Type: {page_type}\n"
    try:
        if log_path.exists():
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        else:
            log_path.write_text(f"# Wiki Log\n\n{entry}", encoding="utf-8")
        return True
    except Exception:
        return False
