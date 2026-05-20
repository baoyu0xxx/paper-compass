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
