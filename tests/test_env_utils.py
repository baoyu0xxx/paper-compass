import os
from pathlib import Path

from paper_compass.env_utils import load_project_env


def test_load_project_env_overwrites_existing_values(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# comment\nLLM_BASE_URL=https://example.test/v1\nVOLC_EMBED_MODEL=ep-test\nEMPTY_KEY=\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_BASE_URL", "stale-value")
    monkeypatch.setenv("EMPTY_KEY", "stale-empty")

    loaded = load_project_env(env_path)

    assert loaded is True
    assert Path(env_path).exists()
    assert os.environ["LLM_BASE_URL"] == "https://example.test/v1"
    assert os.environ["VOLC_EMBED_MODEL"] == "ep-test"
    assert os.environ["EMPTY_KEY"] == ""


def test_load_project_env_missing_file_is_noop(tmp_path, monkeypatch):
    missing = tmp_path / ".env"
    monkeypatch.setenv("LLM_BASE_URL", "keep-me")

    loaded = load_project_env(missing)

    assert loaded is False
    assert os.environ["LLM_BASE_URL"] == "keep-me"


def test_load_project_env_directory_is_noop(tmp_path, monkeypatch):
    env_dir = tmp_path / ".env"
    env_dir.mkdir()
    monkeypatch.setenv("LLM_BASE_URL", "keep-me")

    loaded = load_project_env(env_dir)

    assert loaded is False
    assert os.environ["LLM_BASE_URL"] == "keep-me"


def test_load_project_env_respects_override_only_without_custom_path(tmp_path, monkeypatch):
    from paper_compass import env_utils

    default = tmp_path / "default.env"
    override = tmp_path / "override.env"
    custom = tmp_path / "custom.env"
    for path in (default, override, custom):
        path.write_text(f"LLM_BASE_URL={path.stem}\n", encoding="utf-8")
    monkeypatch.setattr(env_utils, "DEFAULT_ENV_PATH", default)
    monkeypatch.setenv("PAPER_COMPASS_ENV_PATH", str(override))
    monkeypatch.setenv("LLM_BASE_URL", "stale")

    assert load_project_env() is True
    assert os.environ["LLM_BASE_URL"] == "override"
    assert load_project_env(custom) is True
    assert os.environ["LLM_BASE_URL"] == "custom"
    monkeypatch.delenv("PAPER_COMPASS_ENV_PATH")
    assert load_project_env(None) is True
    assert os.environ["LLM_BASE_URL"] == "default"


def test_default_env_path_distinguishes_source_and_wheel(tmp_path, monkeypatch):
    import runpy
    from paper_compass import resources
    from paper_compass import env_utils

    root = tmp_path / "wheel"
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(resources, "project_root", lambda: root)
    monkeypatch.setenv("PAPER_COMPASS_ROOT", str(runtime))
    wheel = runpy.run_path(env_utils.__file__)
    assert wheel["PROJECT_ROOT"] == root
    assert wheel["DEFAULT_ENV_PATH"] == runtime / ".env"

    monkeypatch.delenv("PAPER_COMPASS_ROOT")
    wheel = runpy.run_path(env_utils.__file__)
    assert wheel["DEFAULT_ENV_PATH"] == Path.home() / ".paper-compass" / ".env"

    (root / "src" / "paper_compass").mkdir(parents=True)
    (root / "pyproject.toml").touch()
    monkeypatch.setenv("PAPER_COMPASS_ROOT", str(runtime))
    source = runpy.run_path(env_utils.__file__)
    assert source["DEFAULT_ENV_PATH"] == root / ".env"
