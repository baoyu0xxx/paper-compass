"""
Wiki query module for paper-compass.

Searches the local markdown wiki for knowledge breadth retrieval.
Provides keyword search, page-type filtering, and snippet extraction.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── wiki metadata ─────────────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> Dict[str, Any]:
    """Parse YAML-like frontmatter from a markdown page."""
    fm: Dict[str, Any] = {}
    lines = content.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            line = lines[i].strip()
            if line == "---":
                break
            if ":" in line:
                key, _, value = line.partition(":")
                fm[key.strip()] = value.strip()

    # Extract title from first heading if not in frontmatter
    if "title" not in fm:
        for line in lines:
            m = re.match(r"^#\s+(.+)", line)
            if m:
                fm["title"] = m.group(1).strip()
                break

    return fm


def _extract_snippet(content: str, query: str, context_chars: int = 120) -> str:
    """Extract a snippet of text around the first occurrence of query."""
    if not query:
        # Return first non-empty, non-heading paragraph
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and len(stripped) > 20:
                return stripped[:context_chars]
        return ""

    lower_content = content.lower()
    lower_query = query.lower()
    idx = lower_content.find(lower_query)
    if idx == -1:
        # Return first substantial paragraph
        return _extract_snippet(content, "")

    start = max(0, idx - context_chars // 2)
    end = min(len(content), idx + len(query) + context_chars // 2)
    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    return snippet


def _get_page_type(page_path: Path, wiki_root: Path) -> str:
    """Infer page type from its directory within the wiki."""
    try:
        rel = page_path.relative_to(wiki_root)
        parts = rel.parts
        if len(parts) > 1:
            return parts[0]
    except ValueError:
        pass
    return "unknown"


# ── search ────────────────────────────────────────────────────────────────────

def search_wiki_pages(
    query: str,
    wiki_root: str = "./wiki",
    limit: int = 5,
    page_types: Optional[List[str]] = None,
    return_snippets: bool = True,
) -> List[Dict[str, Any]]:
    """Search wiki pages by keyword.

    Args:
        query: Search query string.
        wiki_root: Path to the wiki directory.
        limit: Max number of results.
        page_types: Filter by page types (e.g. ['topics', 'methods']).
        return_snippets: Whether to include text snippets.

    Returns:
        List of match dicts with page_path, title, page_type, summary, snippet, score.
    """
    root = Path(wiki_root)
    if not root.exists():
        return []

    query_lower = query.lower()
    query_terms = query_lower.split()
    results: List[Dict[str, Any]] = []

    for md_file in sorted(root.rglob("*.md")):
        # Skip hidden/schema files
        if md_file.name.startswith("."):
            continue

        # Filter by page type
        ptype = _get_page_type(md_file, root)
        if page_types and ptype not in page_types:
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        content_lower = content.lower()

        # Score: number of term matches (weighted)
        score = 0
        for term in query_terms:
            count = content_lower.count(term)
            score += count

        # Bonus for title/heading match
        for line in content.split("\n"):
            if line.strip().startswith("#") and query_lower in line.lower():
                score += 5
                break

        if score == 0:
            continue

        # Parse frontmatter
        fm = _parse_frontmatter(content)

        results.append(
            {
                "page_path": str(md_file),
                "title": fm.get("title", md_file.stem),
                "page_type": ptype,
                "summary": fm.get("summary", ""),
                "snippet": _extract_snippet(content, query) if return_snippets else "",
                "score": score,
            }
        )

    # Sort by score descending
    results.sort(key=lambda r: r["score"], reverse=True)

    return results[:limit]


def answer_from_wiki(
    query: str,
    wiki_root: str = "./wiki",
    max_pages: int = 3,
    page_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate a breadth-level answer from wiki pages.

    Args:
        query: The research question.
        wiki_root: Wiki directory path.
        max_pages: Max wiki pages to aggregate.
        page_types: Optional page type filter.

    Returns:
        Dict with answer_text, pages_used, confidence.
    """
    matches = search_wiki_pages(
        query,
        wiki_root=wiki_root,
        limit=max_pages,
        page_types=page_types,
        return_snippets=True,
    )

    if not matches:
        return {
            "answer_text": "Wiki contains no relevant information for this query.",
            "pages_used": [],
            "confidence": "low",
            "query_interpretation": "broad wiki lookup — no matches",
        }

    # Build a simple aggregated answer from snippets
    snippets = []
    for m in matches:
        snippets.append(
            f"From [{m['title']}]({m['page_path']}): {m['snippet']}"
        )

    # Determine confidence
    if len(matches) >= 2 and matches[0]["score"] > 3:
        confidence = "medium"
    elif matches[0]["score"] > 5:
        confidence = "high"
    else:
        confidence = "low"

    answer_text = (
        f"Wiki search found {len(matches)} relevant page(s):\n\n"
        + "\n\n".join(snippets)
    )

    if confidence == "low":
        answer_text += (
            "\n\nNote: Wiki confidence is low. "
            "Consider escalating to PDF retrieval for detailed evidence."
        )

    return {
        "answer_text": answer_text,
        "pages_used": [
            {
                "page_path": m["page_path"],
                "title": m["title"],
                "page_type": m["page_type"],
            }
            for m in matches
        ],
        "confidence": confidence,
        "query_interpretation": "broad wiki lookup",
    }
