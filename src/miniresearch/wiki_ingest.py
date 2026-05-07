"""
Wiki ingest module for paper-compass.

Handles writing curated research results back into the local markdown wiki.
Updates index.md and log.md automatically.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── helpers ───────────────────────────────────────────────────────────────────

def _slugify(title: str) -> str:
    """Convert a title to a filename-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug[:80]


def _generate_filename(title: str, target_type: str) -> str:
    """Generate a wiki page filename with date prefix."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(title)
    return f"{date_str}-{slug}.md"


def _format_frontmatter(fields: Dict[str, Any]) -> str:
    """Format YAML-like frontmatter block."""
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


# ── wiki writeback ────────────────────────────────────────────────────────────

def save_query_to_wiki(
    title: str,
    content: str,
    target_type: str = "queries",
    source_refs: Optional[List[str]] = None,
    confidence: str = "medium",
    tags: Optional[List[str]] = None,
    wiki_root: str = "./wiki",
) -> Dict[str, Any]:
    """Save a curated query result to the wiki.

    Args:
        title: Page title.
        content: Markdown content body.
        target_type: Page type (queries, topics, methods, comparisons).
        source_refs: References to wiki pages or doc_ids.
        confidence: Confidence level (high, medium, low).
        tags: Optional tag list.
        wiki_root: Wiki root directory.

    Returns:
        Dict with page_path, created, linked_pages, log_updated, index_updated.
    """
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

    # Build frontmatter
    frontmatter = _format_frontmatter(
        {
            "title": title,
            "created": now,
            "updated": now,
            "type": target_type,
            "tags": tags,
            "sources": source_refs,
            "confidence": confidence,
        }
    )

    full_content = f"{frontmatter}\n\n# {title}\n\n{content}\n"

    # Write page
    page_path.write_text(full_content, encoding="utf-8")

    # Extract linked wiki pages (those starting with wiki/)
    linked_pages = [ref for ref in source_refs if ref.startswith("wiki/")]

    # Update index.md
    index_path = root / "index.md"
    index_updated = _update_index(index_path, title, target_type, filename)

    # Update log.md
    log_path = root / "log.md"
    log_updated = _update_log(log_path, title, target_type, str(page_path))

    return {
        "page_path": str(page_path),
        "created": True,
        "linked_pages": linked_pages,
        "log_updated": log_updated,
        "index_updated": index_updated,
    }


def _update_index(
    index_path: Path, title: str, page_type: str, filename: str
) -> bool:
    """Add a new page entry to the wiki index.md under the correct section."""
    if not index_path.exists():
        return False

    try:
        content = index_path.read_text(encoding="utf-8")
    except Exception:
        return False

    # Find the section header for this page type
    section_pattern = re.compile(
        rf"^##\s+{re.escape(page_type.capitalize())}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = section_pattern.search(content)
    if not match:
        # Try without capitalization
        section_pattern = re.compile(
            rf"^##\s+{re.escape(page_type)}\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        match = section_pattern.search(content)

    if not match:
        return False  # Can't find the section — skip index update

    insert_pos = match.end()

    # Check if already linked
    link = f"[{title}]({page_type}/{filename})"
    if link in content:
        return False  # Already present

    # Insert the link after the section header
    new_content = (
        content[:insert_pos]
        + f"\n- {link}"
        + content[insert_pos:]
    )
    index_path.write_text(new_content, encoding="utf-8")
    return True


def _update_log(
    log_path: Path, title: str, page_type: str, page_path_str: str
) -> bool:
    """Append a log entry to the wiki log.md."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n## [{date_str}] writeback | {page_type}\n"
        f"- Page: [{title}]({page_path_str})\n"
        f"- Type: {page_type}\n"
    )

    try:
        if log_path.exists():
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        else:
            log_path.write_text(
                f"# Wiki Log\n\n{entry}", encoding="utf-8"
            )
        return True
    except Exception:
        return False
