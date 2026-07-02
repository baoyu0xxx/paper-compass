from __future__ import annotations

import builtins
import importlib
import sys
from types import ModuleType, SimpleNamespace


class _ImportBlocker:
    def __init__(self, blocked: set[str]):
        self.blocked = blocked

    def __call__(self, name: str, *args, **kwargs):
        if name in self.blocked:
            raise ImportError(f"No module named '{name}'")
        return self.original(name, *args, **kwargs)


def test_document_extract_import_does_not_require_markitdown(monkeypatch):
    sys.modules.pop("paper_compass.document_extract", None)
    sys.modules.pop("markitdown", None)
    blocker = _ImportBlocker({"markitdown"})
    blocker.original = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", blocker)

    module = importlib.import_module("paper_compass.document_extract")

    assert hasattr(module, "extract_document")


def test_fake_markitdown_backend_returns_text_and_metadata(monkeypatch, tmp_path):
    from paper_compass import document_extract

    doc = tmp_path / "paper.docx"
    doc.write_text("binary-ish", encoding="utf-8")

    fake_module = ModuleType("markitdown")

    class FakeMarkItDown:
        def convert(self, path):
            assert path == str(doc)
            return SimpleNamespace(text_content="converted document text")

    fake_module.MarkItDown = FakeMarkItDown
    monkeypatch.setitem(sys.modules, "markitdown", fake_module)

    result = document_extract.extract_document(doc)

    assert result.text == "converted document text"
    assert result.backend == "markitdown"
    assert result.source_path == str(doc)
    assert result.reason == ""


def test_max_chars_truncates_markitdown_result(monkeypatch, tmp_path):
    from paper_compass import document_extract

    doc = tmp_path / "notes.md"
    doc.write_text("ignored", encoding="utf-8")

    fake_module = ModuleType("markitdown")

    class FakeMarkItDown:
        def convert(self, path):
            return SimpleNamespace(text_content="abcdef")

    fake_module.MarkItDown = FakeMarkItDown
    monkeypatch.setitem(sys.modules, "markitdown", fake_module)

    result = document_extract.extract_document(doc, max_chars=3)

    assert result.text == "abc"
    assert result.backend == "markitdown"


def test_non_pdf_missing_markitdown_returns_empty_with_reason(monkeypatch, tmp_path):
    from paper_compass import document_extract

    doc = tmp_path / "paper.docx"
    doc.write_text("binary-ish", encoding="utf-8")
    monkeypatch.delitem(sys.modules, "markitdown", raising=False)
    monkeypatch.setattr(document_extract, "_load_markitdown_class", lambda: None, raising=False)

    result = document_extract.extract_document(doc)

    assert result.text == ""
    assert result.backend == "none"
    assert result.source_path == str(doc)
    assert "markitdown" in result.reason.lower()
    assert "missing" in result.reason.lower() or "unavailable" in result.reason.lower()


def test_pdf_fallback_uses_pdfextractor_when_markitdown_unavailable(monkeypatch, tmp_path):
    from paper_compass import document_extract

    pdf = tmp_path / "paper.pdf"
    pdf.write_text("pdf", encoding="utf-8")
    monkeypatch.setattr(document_extract, "_load_markitdown_class", lambda: None, raising=False)

    class FakePDFExtractor:
        def __init__(self, filepath):
            self.filepath = filepath

        def extract_all_text(self):
            assert self.filepath == str(pdf)
            return "pdf fallback text"

    monkeypatch.setattr(document_extract, "PDFExtractor", FakePDFExtractor, raising=False)

    result = document_extract.extract_document(pdf)

    assert result.text == "pdf fallback text"
    assert result.backend == "pdf"
    assert result.reason == ""


def test_pdf_fallback_uses_pdfextractor_when_markitdown_returns_empty(monkeypatch, tmp_path):
    from paper_compass import document_extract

    pdf = tmp_path / "paper.pdf"
    pdf.write_text("pdf", encoding="utf-8")

    fake_module = ModuleType("markitdown")

    class FakeMarkItDown:
        def convert(self, path):
            return SimpleNamespace(text_content="   ")

    fake_module.MarkItDown = FakeMarkItDown
    monkeypatch.setitem(sys.modules, "markitdown", fake_module)

    class FakePDFExtractor:
        def __init__(self, filepath):
            self.filepath = filepath

        def extract_all_text(self):
            return "pdf fallback after empty markitdown"

    monkeypatch.setattr(document_extract, "PDFExtractor", FakePDFExtractor, raising=False)

    result = document_extract.extract_document(pdf, preferred_backend="markitdown")

    assert result.text == "pdf fallback after empty markitdown"
    assert result.backend == "pdf"
    assert "markitdown" in result.reason.lower()
