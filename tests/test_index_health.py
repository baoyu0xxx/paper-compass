from __future__ import annotations


def test_inspect_index_health_reports_ok_for_missing_db(tmp_path):
    from paper_compass.index_health import inspect_index_health

    report = inspect_index_health(tmp_path / "vectordb")

    assert report.ok is True
    assert report.severity == "ok"
    assert report.chroma_openable is True
    assert report.has_journal is False
    assert report.has_wal is False
    assert report.has_shm is False


def test_inspect_index_health_flags_journal_warning(tmp_path):
    from paper_compass.index_health import inspect_index_health

    db_path = tmp_path / "vectordb"
    db_path.mkdir()
    (db_path / "chroma.sqlite3-journal").write_text("pending", encoding="utf-8")

    report = inspect_index_health(db_path)

    assert report.ok is False
    assert report.severity == "warning"
    assert report.has_journal is True
    assert "journal" in report.summary.lower()
    assert "rebuild" in report.recommended_action.lower() or "backup" in report.recommended_action.lower()


def test_inspect_index_health_flags_corruption_when_client_open_fails(tmp_path, monkeypatch):
    from paper_compass import index_health

    class BrokenClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("metadata segment broken")

    monkeypatch.setattr(index_health, "_create_persistent_client", BrokenClient)

    report = index_health.inspect_index_health(tmp_path / "vectordb")

    assert report.ok is False
    assert report.severity == "corrupted"
    assert report.chroma_openable is False
    assert "metadata segment broken" in report.summary


def test_inspect_index_health_collects_manifest_files(tmp_path, monkeypatch):
    from paper_compass import index_health

    db_path = tmp_path / "vectordb"
    db_path.mkdir()
    (db_path / "papers_fake.manifest.json").write_text('{"items": {}}', encoding="utf-8")
    (db_path / "wiki_fake.manifest.json").write_text('{"items": {}}', encoding="utf-8")

    class DummyCollection:
        def __init__(self, name: str, count: int):
            self.name = name
            self._count = count

        def count(self) -> int:
            return self._count

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_collections(self):
            return [DummyCollection("papers_fake", 12), DummyCollection("wiki_fake", 5)]

    monkeypatch.setattr(index_health, "_create_persistent_client", DummyClient)

    report = index_health.inspect_index_health(db_path)

    assert report.chroma_openable is True
    assert report.manifest_files == ["papers_fake.manifest.json", "wiki_fake.manifest.json"]
    assert report.collection_counts == {"papers_fake": 12, "wiki_fake": 5}


def test_inspect_index_health_marks_invalid_manifest_as_corrupted(tmp_path, monkeypatch):
    from paper_compass import index_health

    db_path = tmp_path / "vectordb"
    db_path.mkdir()
    (db_path / "papers_fake.manifest.json").write_text("not-json", encoding="utf-8")

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_collections(self):
            return []

    monkeypatch.setattr(index_health, "_create_persistent_client", DummyClient)

    report = index_health.inspect_index_health(db_path)

    assert report.ok is False
    assert report.severity == "corrupted"
    assert "manifest" in report.summary.lower()
