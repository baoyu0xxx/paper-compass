"""Unified document text extraction for paper-compass.

The MarkItDown dependency is optional and intentionally imported lazily. PDF
extraction keeps the existing PyMuPDF/pdfplumber path through ``PDFExtractor`` as
its robust fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ExtractResult:
    text: str
    backend: str
    source_path: str
    reason: str = ""


class ExtractionError(Exception):
    """Raised by callers that choose to treat extraction failures as fatal."""


# Test seam: tests may monkeypatch this symbol to avoid importing real PDF deps.
PDFExtractor: Any | None = None


def _truncate(text: str, max_chars: int | None) -> str:
    if max_chars is None:
        return text
    return text[:max_chars]


def _load_markitdown_class() -> Any | None:
    try:
        from markitdown import MarkItDown
    except ImportError:
        return None
    return MarkItDown


def _markitdown_text(converted: Any) -> str:
    for attr in ("text_content", "markdown", "text"):
        value = getattr(converted, attr, None)
        if isinstance(value, str):
            return value
    if isinstance(converted, str):
        return converted
    return ""


def _extract_with_markitdown(path: Path) -> tuple[str, str]:
    markitdown_cls = _load_markitdown_class()
    if markitdown_cls is None:
        return "", "markitdown missing"

    converter = markitdown_cls()
    converted = converter.convert(str(path))
    return _markitdown_text(converted), ""


def _extract_pdf_with_fallback(path: Path) -> str:
    extractor_cls = PDFExtractor
    if extractor_cls is None:
        from paper_compass.pdf_extract import PDFExtractor as extractor_cls
    return extractor_cls(str(path)).extract_all_text()


def extract_document(
    path: str | Path,
    *,
    preferred_backend: str | None = None,
    max_chars: int | None = None,
) -> ExtractResult:
    """Extract text from a document using MarkItDown when useful and PDF fallback.

    Non-PDF formats require optional MarkItDown support. If MarkItDown is not
    installed for a non-PDF, the function returns an empty structured result
    rather than raising, preserving the calling scripts' empty-text semantics.
    """

    source = Path(path)
    source_path = str(source)
    suffix = source.suffix.lower()
    is_pdf = suffix == ".pdf"
    preferred = preferred_backend.lower() if preferred_backend else None

    should_try_markitdown = preferred == "markitdown" or not is_pdf
    if is_pdf and preferred != "pdf" and _load_markitdown_class() is not None:
        should_try_markitdown = True

    markitdown_reason = ""
    if should_try_markitdown:
        try:
            text, markitdown_reason = _extract_with_markitdown(source)
        except Exception as exc:
            markitdown_reason = f"markitdown error: {exc}"
        else:
            if text.strip():
                return ExtractResult(
                    text=_truncate(text, max_chars),
                    backend="markitdown",
                    source_path=source_path,
                )
            if not markitdown_reason:
                markitdown_reason = "markitdown returned empty text"

    if is_pdf:
        text = _extract_pdf_with_fallback(source)
        reason = markitdown_reason if markitdown_reason and should_try_markitdown else ""
        return ExtractResult(
            text=_truncate(text, max_chars),
            backend="pdf",
            source_path=source_path,
            reason=reason,
        )

    reason = markitdown_reason or "markitdown missing or unsupported document type"
    return ExtractResult(
        text="",
        backend="none",
        source_path=source_path,
        reason=reason,
    )
