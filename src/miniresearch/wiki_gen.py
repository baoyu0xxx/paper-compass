"""
LLM-driven wiki page generator for paper-compass.

Takes extracted PDF text → calls LLM (Mimo) with ingest prompt → produces
structured markdown wiki pages with frontmatter.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from miniresearch.config import get_provider_config, load_all_configs

logger = logging.getLogger(__name__)


class WikiGenerator:
    """Generate wiki pages from paper text using an LLM.

    Uses the wiki_generation provider from configs/providers.yaml.
    """

    def __init__(self, config_dir: str = "configs"):
        self._configs = load_all_configs(config_dir)
        self._provider = get_provider_config("wiki_generation", self._configs)
        self._ingest_prompt = self._load_prompt("prompts/wiki_ingest.md")

    def _load_prompt(self, path: str) -> str:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    def generate(
        self,
        title: str,
        paper_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        max_input_chars: int = 8000,
    ) -> Dict[str, Any]:
        """Generate a wiki page from a paper's extracted text.

        Args:
            title: Paper title.
            paper_text: Full or partial text extracted from the PDF.
            metadata: Optional metadata (authors, year, doi, etc.).
            max_input_chars: Max chars from paper_text to send to LLM.

        Returns:
            Dict with: title, content (markdown), target_type, tags, confidence.
        """
        if metadata is None:
            metadata = {}

        # Truncate input
        text_snippet = paper_text[:max_input_chars]

        # Build user prompt
        authors = ", ".join(metadata.get("authors", [])) or "(unknown)"
        year = metadata.get("year") or metadata.get("date", "")[:4] or "(n.d.)"
        doi = metadata.get("doi", "")

        user_prompt = f"""Analyze the following academic paper and create a concise wiki page entry for a personal research wiki.

Paper: {title}
Authors: {authors}
Year: {year}
DOI: {doi}

Extracted text (first {max_input_chars} chars):
---
{text_snippet}
---

Create a wiki page with:
1. Research Focus (1-2 sentences on what the paper studies)
2. Key Methodology (brief description of approach, data, identification)
3. Main Findings (2-4 key results, with cautious academic tone — use "suggests", "finds evidence that", "reports a positive association" etc.)
4. Relevance to my research (how this connects to family firm succession, labor structure, DID, or related topics if applicable)
5. Open Questions or limitations mentioned by the authors

Output ONLY valid YAML frontmatter + markdown body. Use tags from: identification, DID, event-study, family-firm, labor, management, China, innovation, AI, governance, methodology.

Frontmatter must include: title, type (topics/methods/papers), tags (list), confidence (high/medium/low)."""

        content = self._call_llm(user_prompt)

        # Parse frontmatter vs body
        fm, body = self._split_frontmatter(content, title)

        return {
            "title": fm.get("title", title),
            "content": body,
            "target_type": fm.get("type", "topics"),
            "tags": fm.get("tags", []),
            "confidence": fm.get("confidence", "medium"),
        }

    def _call_llm(self, user_prompt: str) -> str:
        """Call the LLM API (Mimo OpenAI-compatible endpoint)."""
        base_url = self._provider.get("base_url", "").rstrip("/")
        api_key = self._provider.get("api_key", "")
        model = self._provider.get("model", "mimo-v2.5-pro")

        messages = []
        if self._ingest_prompt:
            messages.append({"role": "system", "content": self._ingest_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2000,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]

    @staticmethod
    def _split_frontmatter(text: str, fallback_title: str) -> tuple:
        """Split LLM output into (frontmatter_dict, body_markdown)."""
        fm: Dict[str, Any] = {"title": fallback_title, "type": "topics", "tags": [], "confidence": "medium"}
        body = text

        # Try YAML frontmatter
        lines = text.split("\n")
        if lines and lines[0].strip() == "---":
            end_idx = None
            for i in range(1, min(len(lines), 30)):
                if lines[i].strip() == "---":
                    end_idx = i
                    break
            if end_idx:
                fm_block = "\n".join(lines[1:end_idx])
                for line in fm_block.split("\n"):
                    line = line.strip()
                    if ":" in line and not line.startswith("#"):
                        key, _, val = line.partition(":")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key == "tags" and val.startswith("[") and val.endswith("]"):
                            import re
                            fm[key] = [t.strip().strip('"').strip("'") for t in val[1:-1].split(",") if t.strip()]
                        else:
                            fm[key] = val
                body = "\n".join(lines[end_idx + 1:])

        return fm, body.strip()
