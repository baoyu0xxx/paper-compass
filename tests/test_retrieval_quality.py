"""Retrieval quality regression tests for v1.5 ranking hardening."""

import json
from pathlib import Path

from miniresearch.filters import search_library


def _write_library(path: Path):
    records = [
        {
            "key": "ABC123",
            "title": "Family Firm Succession and Labor Structure",
            "authors": ["Zhang Wei"],
            "year": 2024,
            "doi": "10.1000/family.001",
            "collections": ["family_firm"],
            "tags": ["DID", "labor"],
            "pdf_path": "a.pdf",
        },
        {
            "key": "XYZ999",
            "title": "General Corporate Governance Notes",
            "authors": ["Li Ming"],
            "year": 2020,
            "doi": "10.1000/other.999",
            "collections": ["governance"],
            "tags": ["governance"],
            "pdf_path": "b.pdf",
        },
        {
            "key": "DEF456",
            "title": "Family Business and Employment Dynamics",
            "authors": ["Chen Yu"],
            "year": 2023,
            "doi": "10.1000/family.002",
            "collections": ["family_firm"],
            "tags": ["employment"],
            "pdf_path": "c.pdf",
        },
    ]
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def test_exact_key_match_ranked_first(tmp_path):
    lib = tmp_path / "library.json"
    _write_library(lib)

    results = search_library("ABC123", library_path=str(lib), limit=3)
    assert results
    assert results[0]["doc_id"] == "ABC123"


def test_exact_doi_match_ranked_first(tmp_path):
    lib = tmp_path / "library.json"
    _write_library(lib)

    results = search_library("10.1000/family.001", library_path=str(lib), limit=3)
    assert results
    assert results[0]["doi"] == "10.1000/family.001"


def test_exact_normalized_title_match_ranked_first(tmp_path):
    lib = tmp_path / "library.json"
    _write_library(lib)

    results = search_library("family firm succession and labor structure", library_path=str(lib), limit=3)
    assert results
    assert results[0]["title"] == "Family Firm Succession and Labor Structure"
