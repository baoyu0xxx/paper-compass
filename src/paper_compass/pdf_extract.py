"""
PDF text extraction module for paper-compass.

Adapted from RAG-Assistant-for-Zotero backend/pdf.py.
Uses PyMuPDF (fitz) for reliable Chinese + English text extraction from academic PDFs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


class PDFExtractor:
    """Extract text from PDF files for downstream processing (wiki / embedding / RAG).

    Uses PyMuPDF (fitz) — preferred for Chinese academic PDFs with embedded fonts.
    Fallback: pdfplumber for layout-aware extraction.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._path = Path(filepath)

    # ── primary extraction ───────────────────────────────────────────────

    def extract_text(self, max_chars: int = 2000) -> str:
        """Extract up to max_chars of text from the beginning of the PDF."""
        try:
            import fitz
            doc = fitz.open(self.filepath)
            text = ""
            for page in doc:
                text += page.get_text()
                if len(text) >= max_chars:
                    break
            doc.close()
            return text[:max_chars]
        except Exception:
            return self._fallback_extract(max_chars)

    def extract_all_text(self) -> str:
        """Extract full text from all pages as a single string."""
        try:
            import fitz
            doc = fitz.open(self.filepath)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except Exception:
            return self._fallback_extract_all()

    def extract_text_by_page(self) -> List[str]:
        """Extract text as a list of strings, one per page."""
        try:
            import fitz
            doc = fitz.open(self.filepath)
            pages = [page.get_text() for page in doc]
            doc.close()
            return pages
        except Exception:
            return self._fallback_pages()

    def extract_chunks(
        self, max_chars_per_chunk: int = 1500, overlap: int = 200
    ) -> List[Dict[str, Any]]:
        """Extract text as overlapping chunks with page metadata.

        Returns list of dicts: {chunk_id, text, page_num, char_start, char_end}
        """
        pages = self.extract_text_by_page()
        chunks: List[Dict[str, Any]] = []
        chunk_idx = 0

        for page_num, page_text in enumerate(pages, start=1):
            if not page_text.strip():
                continue
            start = 0
            while start < len(page_text):
                end = min(start + max_chars_per_chunk, len(page_text))
                chunk_text = page_text[start:end]
                chunks.append({
                    "chunk_id": f"{self._path.stem}_p{page_num}_c{chunk_idx}",
                    "text": chunk_text,
                    "page_num": page_num,
                    "char_start": start,
                    "char_end": end,
                })
                chunk_idx += 1
                start += max_chars_per_chunk - overlap

        return chunks

    def num_pages(self) -> int:
        """Return total number of pages."""
        try:
            import fitz
            doc = fitz.open(self.filepath)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0

    def get_metadata(self) -> Dict[str, Any]:
        """Get PDF internal metadata (title, author, etc.)."""
        try:
            import fitz
            doc = fitz.open(self.filepath)
            meta = dict(doc.metadata)
            doc.close()
            return meta
        except Exception:
            return {}

    # ── fallbacks ─────────────────────────────────────────────────────────

    def _fallback_extract(self, max_chars: int) -> str:
        try:
            import pdfplumber
            with pdfplumber.open(self.filepath) as pdf:
                text = ""
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t
                    if len(text) >= max_chars:
                        break
            return text[:max_chars]
        except Exception:
            return ""

    def _fallback_extract_all(self) -> str:
        try:
            import pdfplumber
            with pdfplumber.open(self.filepath) as pdf:
                parts = []
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        parts.append(t)
            return "\n".join(parts)
        except Exception:
            return ""

    def _fallback_pages(self) -> List[str]:
        try:
            import pdfplumber
            with pdfplumber.open(self.filepath) as pdf:
                return [
                    page.extract_text() or ""
                    for page in pdf.pages
                ]
        except Exception:
            return []
