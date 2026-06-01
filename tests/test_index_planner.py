from paper_compass.index_planner import plan_paper_index
from paper_compass.index_manifest import build_paper_fingerprint


def _fp(title="Title", text="same text", chunk_count=2):
    item = {
        "key": "A1",
        "title": title,
        "year": 2020,
        "authors": ["A"],
        "collections": ["C"],
        "tags": ["T"],
        "pdf_path": "",
        "text_file": "",
    }
    return build_paper_fingerprint(item, text * 200, "chunks-v1", "embed-v1", chunk_count=chunk_count)


def test_metadata_only_change_does_not_require_embedding():
    current = {"A1": _fp(title="New")}
    previous = {"A1": _fp(title="Old")}

    plan = plan_paper_index(current, previous, {"A1"}, prune_deleted=False)

    assert plan.metadata_only == ["A1"]
    assert plan.requires_embedding == []
    assert plan.process_keys == []


def test_missing_vector_requires_embedding_even_when_manifest_unchanged():
    current = {"A1": _fp()}
    previous = {"A1": _fp()}

    plan = plan_paper_index(current, previous, set(), prune_deleted=False)

    assert plan.missing_in_store == ["A1"]
    assert plan.requires_embedding == ["A1"]
    assert plan.process_keys == ["A1"]


def test_deleted_and_orphan_keys_are_reported_separately():
    current = {"A1": _fp()}
    previous = {"A1": _fp(), "B2": _fp()}

    plan = plan_paper_index(current, previous, {"A1", "C3"}, prune_deleted=True)

    assert plan.deleted == ["B2"]
    assert plan.orphan_in_store == ["C3"]
    assert plan.delete_keys == ["B2", "C3"]


def test_content_change_requires_embedding():
    current = {"A1": _fp(text="new")}
    previous = {"A1": _fp(text="old")}

    plan = plan_paper_index(current, previous, {"A1"}, prune_deleted=False)

    assert plan.content_changed == ["A1"]
    assert plan.requires_embedding == ["A1"]
