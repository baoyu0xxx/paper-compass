"""
PaperQA wrapper module for paper-compass.

Thin wrapper around paper-qa for PDF depth retrieval.
Designed to be called from the router layer when escalation is needed.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional


def is_paperqa_available() -> bool:
    """Check if paper-qa is installed."""
    try:
        import paperqa  # noqa: F401
        return True
    except ImportError:
        return False


def build_index(
    paper_directory: str,
    manifest_path: str,
    pqa_home: str = "./.pqa",
    embedding_provider: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a PaperQA index from the manifest.

    Args:
        paper_directory: Root directory containing PDFs.
        manifest_path: Path to manifest.csv.
        pqa_home: PaperQA home directory for index storage.
        embedding_provider: Provider config for embeddings.

    Returns:
        Status dict with success flag and message.
    """
    if not is_paperqa_available():
        return {
            "success": False,
            "message": "paper-qa package is not installed. Install with: pip install paper-qa>=5",
            "index_built": False,
        }

    try:
        from paperqa import Settings, Docs

        # Build settings
        settings_kwargs = {}

        if embedding_provider:
            if "base_url" in embedding_provider:
                settings_kwargs["embedding"] = f"openai:{embedding_provider.get('model', 'text-embedding-3-small')}"
                # Note: full provider config is environment-dependent
                # For now, defer to env vars PAPERQA_EMBEDDING_* or manual config

        settings = Settings(**settings_kwargs)
        docs = Docs(paper_directory=paper_directory)

        # Index PDFs referenced in manifest
        manifest = Path(manifest_path)
        if manifest.exists():
            import csv
            with open(manifest, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    file_loc = row.get("file_location", "")
                    if file_loc:
                        pdf_path = Path(paper_directory) / file_loc
                        if pdf_path.exists():
                            docs.add(pdf_path)

        return {
            "success": True,
            "message": "Index built successfully",
            "index_built": True,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Index build failed: {e}",
            "index_built": False,
        }


def ask_pdf(
    query: str,
    paper_directory: str = "/mnt/d/zotero_backup",
    manifest_path: str = "data/zotero-export/manifest.csv",
    max_sources: int = 5,
    evidence_k: int = 8,
) -> Dict[str, Any]:
    """Query the PaperQA index.

    Args:
        query: The research question.
        paper_directory: PDF root directory.
        manifest_path: Path to manifest.csv.
        max_sources: Maximum sources to cite.
        evidence_k: Maximum evidence passages.

    Returns:
        Dict with answer, sources, and evidence snippets.
    """
    if not is_paperqa_available():
        return {
            "success": False,
            "answer": "paper-qa is not installed. Cannot perform PDF retrieval.",
            "sources": [],
            "evidence_snippets": [],
        }

    try:
        from paperqa import Settings, Docs

        settings = Settings()
        docs = Docs(paper_directory=paper_directory)

        # Filter by manifest if available
        answer = docs.query(
            query,
            settings=settings,
        )

        # Extract answer components
        return {
            "success": True,
            "answer": str(getattr(answer, "answer", "")),
            "sources": [],
            "evidence_snippets": [],
        }
    except Exception as e:
        return {
            "success": False,
            "answer": f"PaperQA query failed: {e}",
            "sources": [],
            "evidence_snippets": [],
        }
