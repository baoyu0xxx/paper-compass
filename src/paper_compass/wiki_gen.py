"""
LLM-driven wiki page generator for paper-compass.

Two-pass architecture:
  Pass 1 (classify):  wiki_router.md      → paper_type (empirical|theoretical|review|descriptive)
  Pass 2 (generate):  If empirical: wiki_overview.md + wiki_empirical.md
                      If non-empirical: wiki_overview.md only
                      Fallback: wiki_ingest.md (generic)

Prompt files are resolved from WIKI_PROMPT env var:
  - default (or unset): prompts/wiki_overview.md + prompts/wiki_empirical.md
  - economics: prompts/disciplines/economics/
  - custom path: {path}/wiki_overview.md + {path}/wiki_empirical.md

Uses the wiki_generation provider from configs/providers.yaml.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from paper_compass.config import get_provider_config, load_all_configs

logger = logging.getLogger(__name__)


class WikiGenerator:
    """Generate structured wiki pages from paper text using an LLM.

    Automatic two-pass: (1) classify paper type, (2) generate tailored wiki content.

    Prompts are resolved from WIKI_PROMPT env var:
      - "default" (or unset): uses prompts/wiki_overview.md + wiki_empirical.md
      - "economics": uses prompts/disciplines/economics/
      - any path: uses {path}/wiki_overview.md + {path}/wiki_empirical.md
    """

    def __init__(self, config_dir: str = "configs"):
        self._configs = load_all_configs(config_dir)
        self._provider = get_provider_config("wiki_generation", self._configs)

        # Resolve prompt directory from WIKI_PROMPT env var
        prompt_dir = self._resolve_prompt_dir()

        # Prompt files
        self._router_prompt = self._load("prompts/wiki_router.md")
        self._overview_prompt = self._load(f"{prompt_dir}/wiki_overview.md")
        self._empirical_prompt = self._load(f"{prompt_dir}/wiki_empirical.md")
        self._fallback_prompt = self._load("prompts/wiki_ingest.md")

        # Warn if fallback prompts are being used (default prompts missing)
        if not self._overview_prompt and not self._empirical_prompt:
            logger.warning(
                "No prompts found at %s/ — falling back to wiki_ingest.md for all papers. "
                "Run `paper-compass init` to configure wiki prompts, or set WIKI_PROMPT "
                "to a valid prompt directory (default, economics, or a custom path).",
                prompt_dir,
            )

    # ── prompt resolution ─────────────────────────────────────────────────

    def _resolve_prompt_dir(self) -> str:
        """Resolve the prompt directory from WIKI_PROMPT env var.

        Returns a relative or absolute path to the directory containing
        wiki_overview.md and wiki_empirical.md.
        """
        wiki_prompt = os.environ.get("WIKI_PROMPT", "default").strip()
        if not wiki_prompt or wiki_prompt == "default":
            return "prompts"
        elif wiki_prompt in self._available_disciplines():
            return f"prompts/disciplines/{wiki_prompt}"
        else:
            # Custom path — use as-is
            return wiki_prompt

    @staticmethod
    def _available_disciplines() -> list[str]:
        """Discover installed discipline presets under prompts/disciplines/.

        A valid discipline directory must contain wiki_overview.md.
        """
        disciplines_dir = Path("prompts/disciplines")
        if not disciplines_dir.exists() or not disciplines_dir.is_dir():
            return []
        result = []
        try:
            for d in sorted(disciplines_dir.iterdir()):
                if d.is_dir() and (d / "wiki_overview.md").exists():
                    result.append(d.name)
        except OSError:
            pass
        return result

    # ── helpers ───────────────────────────────────────────────────────────

    def _load(self, path: str) -> str:
        p = Path(path)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def _call(self, system_prompt: str, user_prompt: str,
              max_tokens: int = 2500, temperature: float = 0.1,
              max_retries: int = 3) -> str:
        """Call LLM API and return content string.

        Retries on 429 (rate limit) and 5xx (server error) with
        exponential backoff: 1s, 2s, 4s.
        """
        import time

        base_url = self._provider.get("base_url", "").rstrip("/")
        api_key = self._provider.get("api_key", "")
        model = self._provider.get("model", "mimo-v2.5-pro")

        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
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

        last_error = None
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    return result["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                last_error = e
                code = getattr(e, "code", 0)
                if code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    delay = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "API %d on attempt %d/%d — retrying in %ds",
                        code, attempt + 1, max_retries, delay,
                    )
                    time.sleep(delay)
                    continue
                raise

        raise last_error  # type: ignore[misc]

    # ── Pass 1: classification ────────────────────────────────────────────

    def classify(self, title: str, paper_text: str,
                 metadata: Optional[Dict[str, Any]] = None) -> str:
        """Classify paper as empirical, theoretical, review, or descriptive.

        Returns one of: 'empirical', 'theoretical', 'review', 'descriptive'.
        """
        if not self._router_prompt:
            logger.warning("wiki_router.md not found — defaulting to 'empirical'")
            return "empirical"

        authors = ", ".join(metadata.get("authors", [])) if metadata else ""
        year = (metadata or {}).get("year", "")

        user_prompt = (
            f"Paper: {title}\n"
            f"Authors: {authors}\n"
            f"Year: {year}\n\n"
            f"Text (abstract + introduction):\n---\n{paper_text[:4000]}\n---"
        )

        raw = self._call(self._router_prompt, user_prompt, max_tokens=100, temperature=0.0)

        # Parse JSON from response (handle possible markdown wrapping)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            if raw.endswith("```"):
                raw = raw[:-3]
        raw = raw.strip()

        try:
            result = json.loads(raw)
            paper_type = result.get("paper_type", "empirical")
        except json.JSONDecodeError:
            # Fallback: scan response text for keywords
            lower = raw.lower()
            if "theoretical" in lower:
                paper_type = "theoretical"
            elif "review" in lower:
                paper_type = "review"
            elif "descriptive" in lower:
                paper_type = "descriptive"
            else:
                paper_type = "empirical"

        if paper_type not in ("empirical", "theoretical", "review", "descriptive"):
            paper_type = "empirical"

        logger.info("Classified [%s] as '%s'", title[:60], paper_type)
        return paper_type

    # ── Pass 2: generation ────────────────────────────────────────────────

    def generate(
        self,
        title: str,
        paper_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        max_input_chars: int = 12000,
        paper_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a wiki page. Auto-classifies if paper_type not provided.

        Args:
            title: Paper title.
            paper_text: Full or partial PDF text.
            metadata: Optional metadata dict (authors, year, key, etc.).
            max_input_chars: Max chars from paper_text to send.
            paper_type: Override classification. If None, auto-classify via Pass 1.

        Returns:
            Dict with: title, content (markdown), target_type, tags, confidence, paper_type.
        """
        if metadata is None:
            metadata = {}

        text_snippet = paper_text[:max_input_chars]

        # Pass 1: classify if needed
        if paper_type is None:
            paper_type = self.classify(title, paper_text, metadata)

        # Pass 2: compose system prompt based on paper_type
        if paper_type == "empirical":
            system_prompt = (
                self._overview_prompt
                + "\n\n---\n\n"
                + self._empirical_prompt
            )
            max_tok = 3500
        elif paper_type in ("theoretical", "review", "descriptive"):
            system_prompt = self._overview_prompt
            max_tok = 2000
        else:
            # Generic fallback
            system_prompt = self._fallback_prompt
            max_tok = 2000

        # Build user prompt
        authors = ", ".join(metadata.get("authors", [])) or "(unknown)"
        year = metadata.get("year") or metadata.get("date", "")[:4] or "(n.d.)"
        key = metadata.get("key", "")

        user_prompt = (
            f"Paper: {title}\n"
            f"Authors: {authors}\n"
            f"Year: {year}\n"
            f"Zotero Key: {key}\n\n"
            f"Extracted text (first {max_input_chars} chars):\n"
            f"---\n{text_snippet}\n---\n\n"
            f"Paper type (pre-classified): {paper_type}\n"
        )

        if paper_type == "empirical":
            user_prompt += (
                "\nGenerate a complete wiki page with ALL sections "
                "specified in the combined system prompt (including "
                "the Empirical Design section).\n"
            )
        else:
            user_prompt += (
                "\nGenerate a wiki page following the system prompt. "
                "Do NOT include the Empirical Design section since "
                "this is not an empirical paper.\n"
            )

        content = self._call(system_prompt, user_prompt, max_tokens=max_tok)

        # Parse frontmatter vs body
        fm, body = self._split_frontmatter(content, title)
        fm["paper_type"] = paper_type  # ensure paper_type in metadata

        return {
            "title": fm.get("title", title),
            "content": body,
            "target_type": "papers",
            "tags": fm.get("tags", []),
            "confidence": fm.get("confidence", "medium"),
            "paper_type": paper_type,
        }

    # ── frontmatter parsing ───────────────────────────────────────────────

    @staticmethod
    def _split_frontmatter(text: str, fallback_title: str) -> tuple:
        """Split LLM output into (frontmatter_dict, body_markdown).

        Handles both bare YAML frontmatter and code-fenced frontmatter.
        """
        fm: Dict[str, Any] = {
            "title": fallback_title, "type": "paper", "tags": [],
            "confidence": "medium", "paper_type": "empirical",
        }
        body = text

        # Strip outer ``` fences if present
        stripped = text.strip()
        if stripped.startswith("```"):
            first_nl = stripped.find("\n")
            if first_nl > 0:
                stripped = stripped[first_nl + 1:]
            if stripped.endswith("```"):
                stripped = stripped[:-3].strip()

        lines = stripped.split("\n")
        if lines and lines[0].strip() == "---":
            end_idx = None
            for i in range(1, min(len(lines), 40)):
                if lines[i].strip() == "---":
                    end_idx = i
                    break
            if end_idx:
                fm_block = "\n".join(lines[1:end_idx])
                for line in fm_block.split("\n"):
                    line = line.strip()
                    if ":" not in line or line.startswith("#"):
                        continue
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key == "tags":
                        # Handle YAML list: tags:\n  - tag1\n  - tag2
                        # (already handled by looking for ":" in line — but need in-body tags)
                        if val.startswith("[") and val.endswith("]"):
                            fm[key] = [
                                t.strip().strip('"').strip("'")
                                for t in val[1:-1].split(",") if t.strip()
                            ]
                        else:
                            fm[key] = [val]
                    elif key == "authors":
                        if val.startswith("[") and val.endswith("]"):
                            fm[key] = [
                                a.strip().strip('"').strip("'")
                                for a in val[1:-1].split(",") if a.strip()
                            ]
                        else:
                            fm[key] = [val]
                    else:
                        fm[key] = val

                # Also parse tags/authors from YAML list format (indented items)
                in_tags = False
                in_authors = False
                tag_items = []
                author_items = []
                for line in fm_block.split("\n"):
                    line = line.strip()
                    if line == "tags:":
                        in_tags = True
                        in_authors = False
                        continue
                    elif line == "authors:":
                        in_authors = True
                        in_tags = False
                        continue
                    elif line and ":" in line and not line.startswith(" "):
                        in_tags = False
                        in_authors = False
                        continue
                    if in_tags and line.startswith("- "):
                        tag_items.append(line[2:].strip().strip('"').strip("'"))
                    if in_authors and line.startswith("- "):
                        author_items.append(line[2:].strip().strip('"').strip("'"))
                if tag_items:
                    fm["tags"] = tag_items
                if author_items:
                    fm["authors"] = author_items

                body = "\n".join(lines[end_idx + 1:])

        return fm, body.strip()


# ── convenience ────────────────────────────────────────────────────────────────


def load_generator(config_dir: str = "configs") -> WikiGenerator:
    """Factory: load config, initialize provider, return ready-to-use generator."""
    return WikiGenerator(config_dir)
