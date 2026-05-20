from pathlib import Path


def test_repo_and_packaged_config_dirs_have_same_yaml_files():
    repo_root = Path(__file__).resolve().parents[1]
    repo_configs = repo_root / "configs"
    packaged_configs = repo_root / "src" / "paper_compass" / "configs"

    repo_files = {p.name: p for p in repo_configs.glob("*.yaml")}
    packaged_files = {p.name: p for p in packaged_configs.glob("*.yaml")}

    assert repo_files.keys() == packaged_files.keys()

    for name in sorted(repo_files):
        assert repo_files[name].read_text(encoding="utf-8") == packaged_files[name].read_text(encoding="utf-8"), name
