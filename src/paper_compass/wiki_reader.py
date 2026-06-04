"""Readback helpers for wiki page and section content."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from paper_compass.mcp_handles import parse_wiki_handle


def get_wiki_page_section(wiki_handle: str, include_frontmatter: bool = False) -> Dict[str, Any]:
    parsed = parse_wiki_handle(wiki_handle)
    page_path = Path(parsed.page_path)
    if not page_path.exists():
        raise ValueError(f"Wiki page not found: {parsed.page_path}")

    raw_text = page_path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(raw_text)
    content = body
    if parsed.section:
        content = _extract_section(body, parsed.section)
    if include_frontmatter and frontmatter:
        content = f"{frontmatter}\n\n{content}".strip()

    title = page_path.stem
    heading_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if heading_match:
        title = heading_match.group(1).strip()

    return {
        "wiki_handle": wiki_handle,
        "page_path": str(page_path),
        "section": parsed.section,
        "title": title,
        "content": content.strip(),
    }


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return "", text
    return f"---\n{parts[0][4:]}\n---", parts[1]


def _extract_section(body: str, section: str) -> str:
    lines = body.splitlines()
    collected: list[str] = []
    in_section = False
    target = str(section).strip().lower()
    target_heading = None
    for line in lines:
        if line.startswith("#"):
            heading_text = line.lstrip("#").strip().lower()
            if in_section and line.startswith("##"):
                break
            if heading_text == target or heading_text.replace(" ", "-") == target:
                in_section = True
                target_heading = line
                collected.append(line)
                continue
        if in_section:
            collected.append(line)
    if not collected:
        raise ValueError(f"Wiki section not found: {section}")
    if target_heading is None:
        raise ValueError(f"Wiki section not found: {section}")
    return "\n".join(collected).strip()
