import os
from pathlib import Path

from paper_compass import resources


def test_project_root_resolves_repo_root_from_package_dir(monkeypatch):
    package_dir = Path("/tmp/example-repo/src/paper_compass")
    monkeypatch.setattr(resources, "package_root", lambda: package_dir)

    assert resources.project_root() == Path("/tmp/example-repo")


def test_project_root_resolves_repo_root_from_src_dir(monkeypatch):
    src_dir = Path("/tmp/example-repo/src")
    monkeypatch.setattr(resources, "package_root", lambda: src_dir)

    assert resources.project_root() == Path("/tmp/example-repo")


def test_project_root_falls_back_to_package_root_when_shape_unknown(monkeypatch):
    other_dir = Path("/tmp/example-repo/build-artifact")
    monkeypatch.setattr(resources, "package_root", lambda: other_dir)

    assert resources.project_root() == other_dir


def test_is_source_checkout_requires_both_markers(tmp_path):
    assert resources.is_source_checkout(tmp_path) is False
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert resources.is_source_checkout(tmp_path) is False
    (tmp_path / "src" / "paper_compass").mkdir(parents=True)
    assert resources.is_source_checkout(tmp_path) is True


def test_resolve_stage_script_prefers_existing_source_script(tmp_path, monkeypatch):
    script = tmp_path / "scripts" / "sync_zotero.py"
    script.parent.mkdir()
    script.touch()
    monkeypatch.setattr(resources, "project_root", lambda: tmp_path)
    monkeypatch.setattr(resources.sys, "prefix", str(tmp_path / "prefix"))

    assert resources.resolve_stage_script("sync_zotero.py") == script
    assert resources.resolve_stage_script("sync_zotero.py", root=tmp_path) == script


def test_resolve_stage_script_falls_back_to_installed_data(tmp_path, monkeypatch):
    prefix = tmp_path / "prefix"
    script = prefix / "share" / "paper_compass" / "scripts" / "build_index.py"
    script.parent.mkdir(parents=True)
    script.touch()
    monkeypatch.setattr(resources.sys, "prefix", str(prefix))

    assert resources.resolve_stage_script("build_index.py", root=tmp_path / "wheel") == script


def test_setuptools_installs_stage_scripts_as_data_files():
    import tomllib

    config = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["setuptools"]["data-files"]["share/paper_compass/scripts"] == [
        "scripts/sync_zotero.py", "scripts/build_index.py", "scripts/ingest_to_wiki.py"
    ]
