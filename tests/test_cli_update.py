"""Tests for the paper-compass update command."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

# Use the project's update module (imported after src/ is on path)
from paper_compass.cli.update import (
    _detect_config_schema_changes,
    _detect_env_var_changes,
    _ensure_clean_worktree,
    _ensure_git_available,
    _execute_update_impl,
    _get_current_version,
    _get_latest_tag,
    _parse_env_vars,
    _perform_update,
)


# ── _parse_env_vars ──────────────────────────────────────────────────────

class TestParseEnvVars:
    def test_basic_vars(self):
        text = "LLM_BASE_URL=https://api.openai.com/v1\nLLM_API_KEY=sk-1234\n"
        result = _parse_env_vars(text)
        assert result == {"LLM_BASE_URL": False, "LLM_API_KEY": False}

    def test_commented_vars(self):
        text = (
            "LLM_BASE_URL=https://api.openai.com/v1\n"
            "# LLM_MODEL=gpt-4o\n"
            "LLM_API_KEY=sk-1234\n"
        )
        result = _parse_env_vars(text)
        assert result == {
            "LLM_BASE_URL": False,
            "LLM_MODEL": True,
            "LLM_API_KEY": False,
        }

    def test_empty_lines_and_comments(self):
        text = (
            "\n"
            "# This is a comment\n"
            "# LLM_MODEL=gpt-4o\n"
            "EMBED_BASE_URL=https://example.com\n"
            "\n"
        )
        result = _parse_env_vars(text)
        assert result == {"LLM_MODEL": True, "EMBED_BASE_URL": False}

    def test_no_vars(self):
        assert _parse_env_vars("") == {}
        assert _parse_env_vars("# just a comment") == {}

    def test_vars_with_underscores_and_digits(self):
        text = "VOLC_EMBED_API_KEY=key123\nEMBED_MODEL=text-embedding-3-small\n"
        result = _parse_env_vars(text)
        assert result == {"VOLC_EMBED_API_KEY": False, "EMBED_MODEL": False}


# ── _detect_env_var_changes ──────────────────────────────────────────────

class TestDetectEnvVarChanges:
    def test_no_changes(self):
        """Same vars in old and new → no warnings."""
        old = "LLM_BASE_URL=https://api\nLLM_API_KEY=sk\n"
        new = "LLM_BASE_URL=https://api\nLLM_API_KEY=sk\n"
        # We mock _get_file_at_ref since we can't use real git refs
        with mock.patch(
            "paper_compass.cli.update._get_file_at_ref",
            side_effect=[old, new],
        ):
            warnings = _detect_env_var_changes("old", "new")
        assert warnings == []

    def test_new_required_var(self):
        """A new non-commented var is added → warning."""
        old = "LLM_BASE_URL=https://api\n"
        new = "LLM_BASE_URL=https://api\nLLM_MODEL=deepseek-v4-flash\n"
        with mock.patch(
            "paper_compass.cli.update._get_file_at_ref",
            side_effect=[old, new],
        ):
            warnings = _detect_env_var_changes("old", "new")
        assert len(warnings) == 1
        assert "LLM_MODEL" in warnings[0]
        assert "New environment variables" in warnings[0]

    def test_removed_var(self):
        """An old non-commented var is gone → info."""
        old = "LLM_BASE_URL=https://api\nOLD_VAR=value\n"
        new = "LLM_BASE_URL=https://api\n"
        with mock.patch(
            "paper_compass.cli.update._get_file_at_ref",
            side_effect=[old, new],
        ):
            warnings = _detect_env_var_changes("old", "new")
        assert len(warnings) == 1
        assert "OLD_VAR" in warnings[0]
        assert "no longer used" in warnings[0]

    def test_uncommented_var(self):
        """A var that was commented becomes uncommented → warning."""
        old = "LLM_BASE_URL=https://api\n# LLM_MODEL=gpt-4o\n"
        new = "LLM_BASE_URL=https://api\nLLM_MODEL=deepseek-v4-flash\n"
        with mock.patch(
            "paper_compass.cli.update._get_file_at_ref",
            side_effect=[old, new],
        ):
            warnings = _detect_env_var_changes("old", "new")
        assert len(warnings) == 1
        assert "LLM_MODEL" in warnings[0]
        assert "required" in warnings[0].lower()

    def test_added_but_commented_var(self):
        """A new var that is commented out → no warning (optional)."""
        old = "LLM_BASE_URL=https://api\n"
        new = "LLM_BASE_URL=https://api\n# OPTIONAL_VAR=value\n"
        with mock.patch(
            "paper_compass.cli.update._get_file_at_ref",
            side_effect=[old, new],
        ):
            warnings = _detect_env_var_changes("old", "new")
        assert warnings == []

    def test_file_missing(self):
        """If .env.example doesn't exist at one of the refs → no warnings."""
        with mock.patch(
            "paper_compass.cli.update._get_file_at_ref",
            return_value=None,
        ):
            warnings = _detect_env_var_changes("old", "new")
        assert warnings == []


# ── _detect_config_schema_changes ────────────────────────────────────────

class TestDetectConfigSchemaChanges:
    def test_model_to_model_env_migration(self):
        """Detect when providers.yaml changes from hardcoded model to env var."""
        old = "providers:\n  main:\n    model: gpt-4o\n"
        new = "providers:\n  main:\n    model_env: LLM_MODEL\n"
        with mock.patch(
            "paper_compass.cli.update._get_file_at_ref",
            side_effect=[old, new],
        ):
            warnings = _detect_config_schema_changes("old", "new")
        assert len(warnings) == 1
        assert "LLM_MODEL" in warnings[0]
        assert "model_env" in warnings[0] or "env var" in warnings[0].lower()

    def test_no_schema_change(self):
        """Same providers.yaml → no warnings."""
        yaml = "providers:\n  main:\n    model_env: LLM_MODEL\n"
        with mock.patch(
            "paper_compass.cli.update._get_file_at_ref",
            side_effect=[yaml, yaml],
        ):
            warnings = _detect_config_schema_changes("old", "new")
        assert warnings == []

    def test_file_missing(self):
        """providers.yaml doesn't exist → no warnings."""
        with mock.patch(
            "paper_compass.cli.update._get_file_at_ref",
            return_value=None,
        ):
            warnings = _detect_config_schema_changes("old", "new")
        assert warnings == []


# ── _ensure_git_available ────────────────────────────────────────────────

class TestEnsureGitAvailable:
    def test_not_a_git_repo(self, tmp_path):
        """Raises RuntimeError when not in a git repo."""
        with mock.patch(
            "paper_compass.cli.update.PROJECT_ROOT", tmp_path
        ), mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0)
            with pytest.raises(RuntimeError, match="pip install --upgrade paper-compass"):
                _ensure_git_available()

    def test_git_not_found(self, tmp_path):
        """Raises RuntimeError when git is not installed."""
        (tmp_path / ".git").mkdir()
        with mock.patch(
            "paper_compass.cli.update.PROJECT_ROOT", tmp_path
        ), mock.patch(
            "subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            with pytest.raises(RuntimeError, match="git is not available"):
                _ensure_git_available()


# ── _ensure_clean_worktree ───────────────────────────────────────────────

class TestEnsureCleanWorktree:
    def test_clean_tree(self):
        """Clean working tree → no error."""
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(stdout=""),
        ):
            _ensure_clean_worktree(force=False)  # should not raise

    def test_dirty_tree_raises(self):
        """Dirty working tree → RuntimeError."""
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(stdout=" M README.md\n"),
        ):
            with pytest.raises(RuntimeError, match="uncommitted changes"):
                _ensure_clean_worktree(force=False)

    def test_dirty_tree_force(self):
        """Dirty tree with --force → no error (just warning)."""
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(stdout=" M README.md\n"),
        ):
            _ensure_clean_worktree(force=True)  # should not raise


# ── _get_current_version ─────────────────────────────────────────────────

class TestGetCurrentVersion:
    def test_from_git_describe(self):
        """Version read from git describe."""
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(returncode=0, stdout="v1.2.4\n"),
        ):
            assert _get_current_version() == "v1.2.4"

    def test_from_git_describe_with_hash(self):
        """git describe returns tag-hash format."""
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(returncode=0, stdout="v1.2.2-2-ga82e3f2\n"),
        ):
            assert _get_current_version() == "v1.2.2-2-ga82e3f2"

    def test_fallback_to_pyproject(self, tmp_path):
        """When git describe fails, fall back to pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "2.0.0"\n')
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(returncode=1, stdout=""),
        ), mock.patch(
            "paper_compass.cli.update.PROJECT_ROOT", tmp_path
        ):
            assert _get_current_version() == "2.0.0"


# ── _get_latest_tag ──────────────────────────────────────────────────────

class TestGetLatestTag:
    def test_sorts_semver_tags(self):
        """Tags are sorted by semver, highest returned."""
        output = (
            "abc123\trefs/tags/v1.2.0\n"
            "def456\trefs/tags/v2.0.0\n"
            "ghi789\trefs/tags/v1.2.4\n"
        )
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(returncode=0, stdout=output),
        ):
            assert _get_latest_tag() == "v2.0.0"

    def test_filters_non_semver_tags(self):
        """Non-semver tags (no v prefix) are ignored."""
        output = (
            "abc123\trefs/tags/release\n"
            "def456\trefs/tags/v1.0.0\n"
        )
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(returncode=0, stdout=output),
        ):
            assert _get_latest_tag() == "v1.0.0"

    def test_no_tags(self):
        """No tags found → empty string."""
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(returncode=0, stdout=""),
        ):
            assert _get_latest_tag() == ""

    def test_git_error(self):
        """Git error → RuntimeError."""
        with mock.patch(
            "paper_compass.cli.update._git",
            return_value=mock.Mock(returncode=1, stderr="fatal: ..."),
        ):
            with pytest.raises(RuntimeError, match="Failed to fetch tags"):
                _get_latest_tag()


# ── CLI argument parsing ─────────────────────────────────────────────────

class TestCliArgParsing:
    def test_subcommand_registered(self):
        """update subcommand is registered in the main CLI."""
        from paper_compass.cli import main

        with mock.patch.object(sys, "argv", ["paper-compass", "update", "--help"]):
            with mock.patch("sys.stdout", io.StringIO()) as fake_out:
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                output = fake_out.getvalue()
                assert "--check" in output
                assert "--version" in output
                assert "--force" in output
                assert "--dry-run" in output

    def test_check_mode_flag(self):
        """--check flag is accepted."""
        parser = _make_parser()
        args = parser.parse_args(["--check"])
        assert args.check is True
        assert args.dry_run is False

    def test_version_flag(self):
        """--version flag accepts a version string."""
        parser = _make_parser()
        args = parser.parse_args(["--version", "v1.3.0"])
        assert args.version == "v1.3.0"

    def test_force_flag(self):
        """--force flag is accepted."""
        parser = _make_parser()
        args = parser.parse_args(["--force"])
        assert args.force is True

    def test_dry_run_flag(self):
        """--dry-run flag is accepted."""
        parser = _make_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True


class TestExecuteUpdateImpl:
    def test_check_mode_reports_available_changes_without_updating(self):
        args = _make_parser().parse_args(["--check"])

        with mock.patch("paper_compass.cli.update._ensure_git_available"), mock.patch(
            "paper_compass.cli.update._get_current_version", return_value="v1.2.0"
        ), mock.patch(
            "paper_compass.cli.update._git", return_value=mock.Mock(returncode=0)
        ), mock.patch(
            "paper_compass.cli.update._get_target_version", return_value="v1.3.0"
        ), mock.patch(
            "paper_compass.cli.update._get_changelog",
            return_value="abc123 feat: improve sync",
        ), mock.patch(
            "paper_compass.cli.update._perform_update"
        ) as perform_update, mock.patch("sys.stdout", io.StringIO()) as fake_out:
            rc = _execute_update_impl(args)

        assert rc == 0
        perform_update.assert_not_called()
        output = fake_out.getvalue()
        assert "Current version: v1.2.0" in output
        assert "Target version:  v1.3.0" in output
        assert "Available changes (v1.2.0 → v1.3.0):" in output
        assert "run 'paper-compass update' to apply this update" in output.lower()

    def test_dry_run_stops_before_perform_update(self):
        args = _make_parser().parse_args(["--dry-run"])

        with mock.patch("paper_compass.cli.update._ensure_git_available"), mock.patch(
            "paper_compass.cli.update._get_current_version", return_value="v1.2.0"
        ), mock.patch(
            "paper_compass.cli.update._git", return_value=mock.Mock(returncode=0)
        ), mock.patch(
            "paper_compass.cli.update._get_target_version", return_value="v1.3.0"
        ), mock.patch(
            "paper_compass.cli.update._detect_breaking_changes",
            return_value=["  ⚠ Example warning"],
        ), mock.patch(
            "paper_compass.cli.update._get_changelog",
            return_value="abc123 feat: improve sync",
        ), mock.patch(
            "paper_compass.cli.update._ensure_clean_worktree"
        ) as ensure_clean, mock.patch(
            "paper_compass.cli.update._perform_update"
        ) as perform_update, mock.patch("sys.stdout", io.StringIO()) as fake_out:
            rc = _execute_update_impl(args)

        assert rc == 0
        ensure_clean.assert_not_called()
        perform_update.assert_not_called()
        output = fake_out.getvalue()
        assert "Updating v1.2.0 → v1.3.0" in output
        assert "⚠ Upgrade notes:" in output
        assert "(dry-run — no changes made)" in output


def test_perform_update_uses_managed_runtime_instead_of_sys_executable(tmp_path):
    managed_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    state = SimpleNamespace(
        managed_python=managed_python,
        managed_exists=True,
        managed_active=True,
        status="active",
    )

    with mock.patch("paper_compass.cli.update._git") as git_cmd, mock.patch(
        "paper_compass.cli.update.ensure_managed_runtime",
        return_value=state,
    ) as ensure_runtime:
        git_cmd.side_effect = [mock.Mock(returncode=0), mock.Mock(returncode=0)]
        assert _perform_update("v1.3.0") is True

    ensure_runtime.assert_called_once()
    kwargs = ensure_runtime.call_args.kwargs
    assert kwargs["project_root"] == Path("D:/pyproject/paper-compass") or kwargs["project_root"]
    assert kwargs["bootstrap_python"] == Path(sys.executable)


def _make_parser():
    import argparse
    from paper_compass.cli.update import add_subcommand_parser

    parser = argparse.ArgumentParser(prog="paper-compass")
    subparsers = parser.add_subparsers(dest="command")
    add_subcommand_parser(subparsers)
    return subparsers.choices["update"]
