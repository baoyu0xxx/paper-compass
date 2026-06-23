from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_ingest_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "ingest_to_wiki.py"
    spec = importlib.util.spec_from_file_location("paper_compass_ingest_to_wiki", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeGenerator:
    def generate(self, title, paper_text, item, max_input_chars=12000):
        return {
            "title": title,
            "content": f"generated for {item['key']}",
            "target_type": "papers",
            "confidence": "medium",
            "tags": [],
        }


def test_process_one_passes_wiki_upsert_mode_to_save(monkeypatch, tmp_path):
    module = _load_ingest_module()
    monkeypatch.chdir(tmp_path)

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")
    text_dir = tmp_path / "data" / "texts"
    text_dir.mkdir(parents=True)
    (text_dir / "A1.txt").write_text("paper text" * 50, encoding="utf-8")

    captured = {}

    def fake_save_query_to_wiki(**kwargs):
        captured.update(kwargs)
        return {"page_path": str(tmp_path / "wiki" / "papers" / "page.md")}

    monkeypatch.setattr(module, "save_query_to_wiki", fake_save_query_to_wiki)

    result = module._process_one(
        {"key": "A1", "title": "Same Title", "pdf_path": str(pdf_path)},
        _FakeGenerator(),
        SimpleNamespace(max_chars=12000, wiki_root=str(tmp_path / "wiki"), wiki_upsert_mode="create_unique"),
    )

    assert result["status"] == "ok"
    assert captured["upsert_mode"] == "create_unique"
