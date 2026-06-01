from __future__ import annotations

from pathlib import Path

from paper_compass.zotero_paths import _default_root_candidates


def test_default_root_candidates_include_userprofile_zotero(monkeypatch, tmp_path):
    userprofile = tmp_path / "User With Space"
    monkeypatch.setenv("USERPROFILE", str(userprofile))

    candidates = _default_root_candidates()

    assert userprofile / "Zotero" in candidates


def test_default_root_candidates_include_git_bash_c_users(monkeypatch, tmp_path):
    c_users = tmp_path / "c" / "Users"
    alice = c_users / "alice"
    (alice / "Zotero").mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", "")
    original_exists = Path.exists
    original_iterdir = Path.iterdir

    def fake_exists(path: Path) -> bool:
        if path == Path("/c/Users"):
            return True
        if path == Path("/mnt/c/Users"):
            return False
        return original_exists(path)

    def fake_iterdir(path: Path):
        if path == Path("/c/Users"):
            return iter(c_users.iterdir())
        return original_iterdir(path)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    candidates = _default_root_candidates()

    assert alice / "Zotero" in candidates
