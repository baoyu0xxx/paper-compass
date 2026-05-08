"""
Wiki writeback store for paper-compass.

Handles writing generated wiki pages to the filesystem with frontmatter
and updating index.md / log.md.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:80]


def _generate_filename(title: str, target_type: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(title)
    return f"{date_str}-{slug}.md"


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


def save_query_to_wiki(
    title: str,
    content: str,
    target_type: str = "queries",
    source_refs: Optional[List[str]] = None,
    confidence: str = "medium",
    tags: Optional[List[str]] = None,
    wiki_root: str = "./wiki",
) -> Dict[str, Any]:
    """Save a wiki page to the filesystem with frontmatter and index/log update."""
    root = Path(wiki_root)
    type_dir = root / target_type
    type_dir.mkdir(parents=True, exist_ok=True)

    if source_refs is None:
        source_refs = []
    if tags is None:
        tags = []

    now = datetime.now(timezone.utc).isoformat()
    filename = _generate_filename(title, target_type)
    page_path = type_dir / filename

    frontmatter = _format_frontmatter({
        "title": title,
        "created": now,
        "updated": now,
        "type": target_type,
        "tags": tags,
        "sources": source_refs,
        "confidence": confidence,
    })

    full_content = f"{frontmatter}\n\n# {title}\n\n{content}\n"
    page_path.write_text(full_content, encoding="utf-8")

    linked_pages = [ref for ref in source_refs if ref.startswith("wiki/")]
    index_updated = _update_index(root / "index.md", title, target_type, filename)
    log_updated = _update_log(root / "log.md", title, target_type, str(page_path))

    return {
        "page_path": str(page_path),
        "created": True,
        "linked_pages": linked_pages,
        "log_updated": log_updated,
        "index_updated": index_updated,
    }


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
