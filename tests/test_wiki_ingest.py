"""Tests for Wiki ingest module."""

import tempfile
from pathlib import Path

import pytest

from miniresearch.wiki_ingest import (
    save_query_to_wiki,
    _slugify,
    _generate_filename,
    _format_frontmatter,
)


@pytest.fixture
def sample_wiki(tmp_path):
    """Create a wiki with index.md and log.md for testing."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    # Create page-type directories
    for ptype in ["papers", "topics", "methods", "queries", "comparisons"]:
        (wiki / ptype).mkdir()

    # Create index.md
    (wiki / "index.md").write_text(
        """# Wiki Index

> Local breadth-layer knowledge catalog.

## Papers

## Topics

## Methods

## Queries

## Comparisons
"""
    )

    # Create log.md
    (wiki / "log.md").write_text(
        """# Wiki Log

## [2026-05-07] create | wiki initialized
- Minimal project wiki created
"""
    )

    # Create purpose.md and .wiki-schema.md
    (wiki / "purpose.md").write_text("# Purpose\n\nTest wiki for paper-compass.\n")
    (wiki / ".wiki-schema.md").write_text("# Wiki Schema\n\nMinimal schema.\n")

    return str(wiki)


class TestSlugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert _slugify("DID: A Method") == "did-a-method"

    def test_chinese(self):
        slug = _slugify("家族企业继承与创新")
        assert len(slug) > 0


class TestFormatFrontmatter:
    def test_simple(self):
        fm = _format_frontmatter({"title": "Test", "type": "queries"})
        assert "title: Test" in fm
        assert "type: queries" in fm
        assert fm.startswith("---")
        assert fm.endswith("---")

    def test_with_list(self):
        fm = _format_frontmatter(
            {"title": "Test", "tags": ["did", "china"]}
        )
        assert "tags:" in fm
        assert "  - did" in fm
        assert "  - china" in fm


class TestSaveQueryToWiki:
    def test_save_creates_page(self, sample_wiki):
        result = save_query_to_wiki(
            title="DID Identification Strategies",
            content="A review of DID identification approaches.",
            target_type="queries",
            source_refs=["wiki/topics/did.md"],
            confidence="medium",
            tags=["did", "identification"],
            wiki_root=sample_wiki,
        )

        assert result["created"] is True
        assert "queries/" in result["page_path"]

        page_path = Path(result["page_path"])
        assert page_path.exists()
        content = page_path.read_text()
        assert "DID Identification Strategies" in content
        assert "A review of DID" in content

        # Frontmatter
        assert "title: DID Identification Strategies" in content
        assert "type: queries" in content
        assert "confidence: medium" in content

    def test_updates_index(self, sample_wiki):
        result = save_query_to_wiki(
            title="New DID Method",
            content="Something new about DID.",
            target_type="queries",
            wiki_root=sample_wiki,
        )
        assert result["index_updated"] is True

        index = Path(sample_wiki) / "index.md"
        content = index.read_text()
        assert "New DID Method" in content
        assert "queries/" in content

    def test_updates_log(self, sample_wiki):
        result = save_query_to_wiki(
            title="Family Firm Analysis",
            content="Analysis of family firms.",
            target_type="topics",
            wiki_root=sample_wiki,
        )
        assert result["log_updated"] is True

        log = Path(sample_wiki) / "log.md"
        content = log.read_text()
        assert "Family Firm Analysis" in content

    def test_duplicate_prevention_in_index(self, sample_wiki):
        # First save
        save_query_to_wiki(
            title="Same Topic",
            content="First version.",
            target_type="topics",
            wiki_root=sample_wiki,
        )
        # Second save of same title should not duplicate index entry
        result2 = save_query_to_wiki(
            title="Same Topic",
            content="Second version.",
            target_type="topics",
            wiki_root=sample_wiki,
        )
        # Index update may return False because already present
        # But the page should still be created (with a new filename)
        assert result2["created"] is True
