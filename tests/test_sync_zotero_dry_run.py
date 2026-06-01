from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_sync_zotero_dry_run_resolves_paths_without_reading_sqlite_or_creating_outputs(tmp_path):
    root = tmp_path / "Zotero Profile #1"
    db_path = root / "zotero.sqlite"
    storage_path = root / "storage"
    storage_path.mkdir(parents=True)
    db_path.write_bytes(b"not a real sqlite database, but enough for path resolution")

    out_dir = tmp_path / "export"
    text_dir = tmp_path / "texts"
    snapshot_dir = tmp_path / "snapshots"

    command = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "scripts" / "sync_zotero.py"),
        "--db-path",
        str(db_path),
        "--storage-path",
        str(storage_path),
        "--out-dir",
        str(out_dir),
        "--text-dir",
        str(text_dir),
        "--snapshot-dir",
        str(snapshot_dir),
        "--extract-text",
        "--dry-run",
    ]

    completed = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True)

    assert completed.returncode == 0, completed.stderr
    assert "Zotero Source Plan" in completed.stdout
    assert str(db_path) in completed.stdout
    assert str(storage_path) in completed.stdout
    assert "Read policy" in completed.stdout
    assert "Reading Zotero database" not in completed.stdout
    assert not out_dir.exists()
    assert not text_dir.exists()
    assert not snapshot_dir.exists()
