from __future__ import annotations

from paper_compass.config import resolve_indexing_settings, resolve_path_settings


def test_path_settings_cli_env_config_precedence(monkeypatch):
    configs = {
        "paths": {
            "paths": {
                "library_json_path": "config/library.json",
                "text_dir": "config/texts",
                "wiki_root": "config/wiki",
                "vectordb_path": "config/vectordb",
                "zotero_sqlite_path": "config/zotero.sqlite",
                "zotero_storage_path": "config/storage",
            }
        }
    }
    monkeypatch.setenv("PAPER_COMPASS_LIBRARY_PATH", "env/library.json")
    monkeypatch.setenv("ZOTERO_SQLITE_PATH", "env/zotero.sqlite")

    settings = resolve_path_settings(
        configs,
        overrides={"library_json_path": "cli/library.json"},
    )

    assert settings.library_json_path == "cli/library.json"
    assert settings.zotero_sqlite_path == "env/zotero.sqlite"
    assert settings.text_dir == "config/texts"
    assert settings.wiki_root == "config/wiki"
    assert settings.vectordb_path == "config/vectordb"
    assert settings.zotero_storage_path == "config/storage"


def test_path_settings_uses_safe_defaults_for_missing_config(monkeypatch):
    monkeypatch.delenv("PAPER_COMPASS_LIBRARY_PATH", raising=False)
    monkeypatch.delenv("PAPER_COMPASS_TEXT_DIR", raising=False)
    monkeypatch.delenv("PAPER_COMPASS_WIKI_ROOT", raising=False)
    monkeypatch.delenv("PAPER_COMPASS_VECTORDB_PATH", raising=False)
    monkeypatch.delenv("ZOTERO_SQLITE_PATH", raising=False)
    monkeypatch.delenv("ZOTERO_STORAGE_PATH", raising=False)

    settings = resolve_path_settings(configs={})

    assert settings.library_json_path == "data/zotero-export/library.json"
    assert settings.text_dir == "data/texts"
    assert settings.wiki_root == "wiki"
    assert settings.vectordb_path == "data/vectordb"
    assert settings.zotero_sqlite_path == ""
    assert settings.zotero_storage_path == ""


def test_indexing_settings_reads_large_incremental_thresholds_from_rag_config():
    configs = {
        "rag": {
            "rag": {
                "indexing": {
                    "large_incremental_change_ratio": 0.5,
                    "large_incremental_change_minimum": 7,
                    "require_dry_run_for_large_incremental": False,
                }
            }
        }
    }

    settings = resolve_indexing_settings(configs)

    assert settings.large_incremental_change_ratio == 0.5
    assert settings.large_incremental_change_minimum == 7
    assert settings.require_dry_run_for_large_incremental is False
