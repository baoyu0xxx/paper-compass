import os
from pathlib import Path

from miniresearch.env_utils import load_project_env


def test_load_project_env_overwrites_existing_values(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# comment\nMIMO_BASE_URL=https://example.test/v1\nVOLC_EMBED_MODEL=ep-test\nEMPTY_KEY=\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MIMO_BASE_URL", "stale-value")
    monkeypatch.setenv("EMPTY_KEY", "stale-empty")

    loaded = load_project_env(env_path)

    assert loaded is True
    assert Path(env_path).exists()
    assert os.environ["MIMO_BASE_URL"] == "https://example.test/v1"
    assert os.environ["VOLC_EMBED_MODEL"] == "ep-test"
    assert os.environ["EMPTY_KEY"] == ""


def test_load_project_env_missing_file_is_noop(tmp_path, monkeypatch):
    missing = tmp_path / ".env"
    monkeypatch.setenv("MIMO_BASE_URL", "keep-me")

    loaded = load_project_env(missing)

    assert loaded is False
    assert os.environ["MIMO_BASE_URL"] == "keep-me"


def test_load_project_env_directory_is_noop(tmp_path, monkeypatch):
    env_dir = tmp_path / ".env"
    env_dir.mkdir()
    monkeypatch.setenv("MIMO_BASE_URL", "keep-me")

    loaded = load_project_env(env_dir)

    assert loaded is False
    assert os.environ["MIMO_BASE_URL"] == "keep-me"
