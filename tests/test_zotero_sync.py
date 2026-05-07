"""Tests for Zotero sync layer."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from miniresearch.zotero import (
    scan_pdf_root,
    build_base_record,
    merge_records,
    load_external_metadata,
    build_manifest_rows,
    write_manifest_csv,
    write_library_json,
    generate_sync_report,
    _normalize_filename,
    _compute_sha256,
)


# ── helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_pdf_dir():
    """Create a temp directory with a few dummy PDF files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        sub = root / "sub"
        sub.mkdir()
        (sub / "paper_a.pdf").write_bytes(b"%PDF-1.4 fake content")
        (sub / "paper_b.pdf").write_bytes(b"%PDF-1.4 another one")
        (sub / "empty.pdf").write_bytes(b"")
        yield str(root)


@pytest.fixture
def sample_metadata_csv():
    """Create a temp metadata CSV file."""
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            "file_name,title,doi,authors,year,journal,collections,tags\n"
            'paper_a.pdf,"Family Businesses in China",10.1234/fbc,"Zhang;Li",2022,"Journal of Management","family_firm;china","did;labor"\n'
            'paper_b.pdf,"Labor Adjustment Dynamics",10.5678/lad,"Wang",2020,"Labor Economics",labor,"did"\n'
        )
        tmp_path = f.name

    yield tmp_path
    Path(tmp_path).unlink(missing_ok=True)


@pytest.fixture
def sample_metadata_json():
    """Create a temp metadata JSON file."""
    import tempfile

    data = [
        {
            "file_name": "paper_a.pdf",
            "title": "Family Businesses in China",
            "doi": "10.1234/fbc",
            "authors": ["Zhang", "Li"],
            "year": 2022,
            "journal": "Journal of Management",
            "collections": ["family_firm", "china"],
            "tags": ["did", "labor"],
        },
        {
            "file_name": "paper_b.pdf",
            "title": "Labor Adjustment Dynamics",
            "doi": "10.5678/lad",
            "authors": ["Wang"],
            "year": 2020,
            "journal": "Labor Economics",
            "collections": ["labor"],
            "tags": ["did"],
        },
    ]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(data, f)
        tmp_path = f.name

    yield tmp_path
    Path(tmp_path).unlink(missing_ok=True)


# ── scan_pdf_root ─────────────────────────────────────────────────────────────

class TestScanPdfRoot:
    def test_scan_finds_pdfs(self, sample_pdf_dir):
        pdfs = scan_pdf_root(sample_pdf_dir)
        # Should find 2 PDFs (empty.pdf is size 0, excluded)
        assert len(pdfs) == 2
        names = {p.name for p in pdfs}
        assert "paper_a.pdf" in names
        assert "paper_b.pdf" in names
        assert "empty.pdf" not in names

    def test_scan_nonexistent_root(self):
        with pytest.raises(FileNotFoundError):
            scan_pdf_root("/nonexistent/pdf/root")


# ── build_base_record ─────────────────────────────────────────────────────────

class TestBuildBaseRecord:
    def test_base_record_fields(self, sample_pdf_dir):
        pdfs = scan_pdf_root(sample_pdf_dir)
        pdf = [p for p in pdfs if p.name == "paper_a.pdf"][0]
        rec = build_base_record(pdf, sample_pdf_dir)

        assert rec["file_name"] == "paper_a.pdf"
        assert rec["relative_path"] == "sub/paper_a.pdf"
        assert rec["file_size"] > 0
        assert "modified_at" in rec
        assert rec["pdf_path"] == str(pdf)


# ── _normalize_filename ───────────────────────────────────────────────────────

class TestNormalizeFilename:
    def test_lowercase(self):
        assert _normalize_filename("Paper_A.PDF") == "paper a"

    def test_separators(self):
        assert _normalize_filename("family-firm_analysis.pdf") == "family firm analysis"

    def test_collapse_spaces(self):
        assert _normalize_filename("a   b--c__.pdf") == "a b c"


# ── _compute_sha256 ───────────────────────────────────────────────────────────

class TestSha256:
    def test_sha256(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            tmp = f.name

        try:
            h = _compute_sha256(tmp)
            assert len(h) == 64
            assert h == _compute_sha256(tmp)  # stable
        finally:
            Path(tmp).unlink()


# ── load_external_metadata ────────────────────────────────────────────────────

class TestLoadMetadata:
    def test_load_csv(self, sample_metadata_csv):
        records = load_external_metadata(sample_metadata_csv)
        assert len(records) == 2
        assert records[0]["title"] == "Family Businesses in China"

    def test_load_json(self, sample_metadata_json):
        records = load_external_metadata(sample_metadata_json)
        assert len(records) == 2
        assert records[0]["title"] == "Family Businesses in China"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_external_metadata("/nonexistent/metadata.csv")


# ── merge_records ─────────────────────────────────────────────────────────────

class TestMergeRecords:
    def test_merge_by_filename(self, sample_pdf_dir, sample_metadata_csv):
        pdfs = scan_pdf_root(sample_pdf_dir)
        base_records = [build_base_record(p, sample_pdf_dir) for p in pdfs]
        meta = load_external_metadata(sample_metadata_csv)
        records = merge_records(base_records, meta, compute_sha=False)

        assert len(records) == 2

        paper_a = [r for r in records if r["file_name"] == "paper_a.pdf"][0]
        assert paper_a["title"] == "Family Businesses in China"
        assert paper_a["doi"] == "10.1234/fbc"
        assert paper_a["authors"] == ["Zhang", "Li"]
        assert paper_a["year"] == 2022
        assert paper_a["collections"] == ["family_firm", "china"]
        assert paper_a["tags"] == ["did", "labor"]
        assert paper_a["metadata_source"] == "external_csv"

    def test_merge_scan_only(self, sample_pdf_dir):
        pdfs = scan_pdf_root(sample_pdf_dir)
        base_records = [build_base_record(p, sample_pdf_dir) for p in pdfs]
        records = merge_records(base_records, None, compute_sha=False)

        assert len(records) == 2
        for r in records:
            assert r["metadata_source"] == "scan_only"
            assert r["file_name"].rsplit(".", 1)[0] in r["title"]  # fallback title

    def test_doc_id_stability(self, sample_pdf_dir):
        pdfs = scan_pdf_root(sample_pdf_dir)
        base_records = [build_base_record(p, sample_pdf_dir) for p in pdfs]
        records1 = merge_records(base_records, [], compute_sha=False)
        records2 = merge_records(base_records, [], compute_sha=False)

        for r1, r2 in zip(records1, records2):
            assert r1["doc_id"] == r2["doc_id"]


# ── manifest.csv ──────────────────────────────────────────────────────────────

class TestManifestCsv:
    def test_build_manifest_rows(self, sample_pdf_dir, sample_metadata_csv):
        pdfs = scan_pdf_root(sample_pdf_dir)
        base_records = [build_base_record(p, sample_pdf_dir) for p in pdfs]
        meta = load_external_metadata(sample_metadata_csv)
        records = merge_records(base_records, meta, compute_sha=False)
        rows = build_manifest_rows(records)

        assert len(rows) == 2
        assert rows[0]["file_location"] in ("sub/paper_a.pdf", "sub/paper_b.pdf")
        assert "file_location" in rows[0]
        assert "title" in rows[0]
        assert "doi" in rows[0]

    def test_write_manifest_csv(self, sample_pdf_dir, sample_metadata_csv):
        import tempfile

        pdfs = scan_pdf_root(sample_pdf_dir)
        base_records = [build_base_record(p, sample_pdf_dir) for p in pdfs]
        meta = load_external_metadata(sample_metadata_csv)
        records = merge_records(base_records, meta, compute_sha=False)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            out_path = f.name

        try:
            count = write_manifest_csv(records, out_path)
            assert count == 2

            with open(out_path, "r") as f:
                header = f.readline().strip()
                assert "file_location" in header
                assert "title" in header
        finally:
            Path(out_path).unlink(missing_ok=True)


# ── library.json ──────────────────────────────────────────────────────────────

class TestLibraryJson:
    def test_write_library_json(self, sample_pdf_dir, sample_metadata_csv):
        import tempfile

        pdfs = scan_pdf_root(sample_pdf_dir)
        base_records = [build_base_record(p, sample_pdf_dir) for p in pdfs]
        meta = load_external_metadata(sample_metadata_csv)
        records = merge_records(base_records, meta, compute_sha=False)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            out_path = f.name

        try:
            count = write_library_json(records, out_path)
            assert count == 2

            with open(out_path, "r") as f:
                data = json.load(f)

            assert isinstance(data, list)
            assert len(data) == 2
            assert "doc_id" in data[0]
            assert "metadata_source" in data[0]

            paper_a = [d for d in data if d["file_name"] == "paper_a.pdf"][0]
            assert paper_a["title"] == "Family Businesses in China"
            assert paper_a["authors"] == ["Zhang", "Li"]
        finally:
            Path(out_path).unlink(missing_ok=True)


# ── sync_report ────────────────────────────────────────────────────────────────

class TestSyncReport:
    def test_report_stats(self, sample_pdf_dir, sample_metadata_csv):
        pdfs = scan_pdf_root(sample_pdf_dir)
        base_records = [build_base_record(p, sample_pdf_dir) for p in pdfs]
        meta = load_external_metadata(sample_metadata_csv)
        records = merge_records(base_records, meta, compute_sha=False)

        report = generate_sync_report(records)
        assert report["total_pdfs"] == 2
        assert report["with_metadata"] == 2
        assert report["scan_only"] == 0
        assert "timestamp" in report

    def test_report_no_metadata(self, sample_pdf_dir):
        pdfs = scan_pdf_root(sample_pdf_dir)
        base_records = [build_base_record(p, sample_pdf_dir) for p in pdfs]
        records = merge_records(base_records, [], compute_sha=False)

        report = generate_sync_report(records)
        assert report["total_pdfs"] == 2
        assert report["with_metadata"] == 0
        assert report["scan_only"] == 2
