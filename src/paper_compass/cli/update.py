"""paper-compass update subcommand.

Checks for and applies updates from the GitHub repository.
Detects breaking changes (new env vars, config schema changes) and guides the user.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from paper_compass.env_utils import DEFAULT_ENV_PATH, PROJECT_ROOT
from paper_compass.runtime_env import ManagedRuntimeError, ensure_managed_runtime

_ENV_VAR_RE = re.compile(r"^(#\s*)?([A-Z][A-Z0-9_]+)=", re.MULTILINE)


# ── Git helpers ───────────────────────────────────────────────────────────

def _git(*args: str, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a git command from PROJECT_ROOT."""
    return subprocess.run(
        ["git", *args],
        capture_output=capture,
        text=True,
        cwd=str(PROJECT_ROOT),
    )


def _ensure_git_available() -> None:
    """Raise RuntimeError if git is not on PATH or we are not in a git repo."""
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise RuntimeError(
            "git is not available. paper-compass update requires git to be installed.\n"
            "See https://git-scm.com/downloads"
        )

    if not (PROJECT_ROOT / ".git").exists():
        raise RuntimeError(
            f"Not a git repository: {PROJECT_ROOT}\n"
            "paper-compass update only works when installed via git clone.\n"
            "If you installed paper-compass from PyPI or a wheel, upgrade with:\n"
            "  python3 -m pip install --upgrade paper-compass"
        )


def _ensure_clean_worktree(force: bool) -> None:
    """Raise RuntimeError if the working tree has uncommitted changes."""
    result = _git("status", "--porcelain")
    if not result.stdout.strip():
        return  # clean

    if force:
        print("  ⚠ Uncommitted changes detected, proceeding due to --force")
        print(f"  Changed files:\n{result.stdout.strip()}")
        return

    raise RuntimeError(
        "Working tree has uncommitted changes. Commit or stash them first,\n"
        "or use --force to proceed anyway.\n\n"
        f"Changed files:\n{result.stdout.strip()}"
    )


# ── Version helpers ───────────────────────────────────────────────────────

def _get_current_version() -> str:
    """Return the current version string (git describe or pyproject.toml)."""
    # Prefer git describe for accuracy
    result = _git("describe", "--tags", "--always")
    if result.returncode == 0:
        return result.stdout.strip()

    # Fall back to pyproject.toml
    try:
        text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "unknown"


def _get_latest_tag() -> str:
    """Return the latest semver tag from the remote, or '' if none found."""
    result = _git("ls-remote", "--tags", "--sort=-version:refname", "origin")
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to fetch tags from remote.\n"
            f"git error: {result.stderr.strip()}"
        )

    # Parse tags like refs/tags/v1.2.4 — pick the highest semver
    semver_tags = []
    for line in result.stdout.strip().splitlines():
        # line looks like: <sha>\trefs/tags/v1.2.4
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        ref = parts[1]
        if ref.startswith("refs/tags/v") and not ref.endswith("^{}"):
            tag = ref[len("refs/tags/"):]
            try:
                # Parse version numbers for sorting
                nums = tuple(int(x) for x in tag.lstrip("v").split("."))
                semver_tags.append((nums, tag))
            except ValueError:
                continue

    if not semver_tags:
        return ""

    semver_tags.sort(key=lambda x: x[0], reverse=True)
    return semver_tags[0][1]


def _get_target_version(args: argparse.Namespace) -> str:
    """Resolve the target version from CLI args or remote tags."""
    if args.version:
        target = args.version
        if not target.startswith("v"):
            target = f"v{target}"
        return target

    latest = _get_latest_tag()
    if not latest:
        raise RuntimeError(
            "No version tags found on remote.\n"
            "Specify a version explicitly with --version, e.g.:\n"
            "  paper-compass update --version v1.2.4"
        )
    return latest


# ── Breaking change detection ─────────────────────────────────────────────

def _parse_env_vars(text: str) -> dict[str, bool]:
    """Parse .env.example text and return {VAR_NAME: is_commented_out}.

    Example: "LLM_BASE_URL=https://..." → {"LLM_BASE_URL": False}
             "# LLM_MODEL=gpt-4o" → {"LLM_MODEL": True}
    """
    vars_: dict[str, bool] = {}
    for match in _ENV_VAR_RE.finditer(text):
        is_commented = match.group(1) is not None
        name = match.group(2)
        vars_[name] = is_commented
    return vars_


def _get_file_at_ref(ref: str, path: str) -> Optional[str]:
    """Get file content from a specific git ref. Returns None if file doesn't exist."""
    result = _git("show", f"{ref}:{path}")
    if result.returncode != 0:
        return None
    return result.stdout


def _detect_env_var_changes(
    old_ref: str, new_ref: str
) -> list[str]:
    """Compare .env.example between two refs and return warnings."""
    old_text = _get_file_at_ref(old_ref, ".env.example")
    new_text = _get_file_at_ref(new_ref, ".env.example")

    if old_text is None or new_text is None:
        return []

    old_vars = _parse_env_vars(old_text)
    new_vars = _parse_env_vars(new_text)

    warnings: list[str] = []

    # New non-commented vars that weren't in old
    added = []
    for name, commented in new_vars.items():
        if name not in old_vars and not commented:
            added.append(name)
    if added:
        warnings.append(
            f"  ⚠ New environment variables may need to be set: {', '.join(added)}\n"
            f"    Compare .env.example to see what values are expected."
        )

    # Old non-commented vars that are gone from new
    removed = []
    for name, commented in old_vars.items():
        if name not in new_vars and not commented:
            removed.append(name)
    if removed:
        warnings.append(
            f"  ℹ The following env vars are no longer used and can be removed: {', '.join(removed)}"
        )

    # Vars that changed from commented to uncommented (new requirement)
    uncommented = []
    for name, commented in new_vars.items():
        if name in old_vars and old_vars[name] and not commented:
            uncommented.append(name)
    if uncommented:
        warnings.append(
            f"  ⚠ Previously optional env vars are now required: {', '.join(uncommented)}\n"
            f"    Check .env.example for the new default values."
        )

    return warnings


def _detect_config_schema_changes(
    old_ref: str, new_ref: str
) -> list[str]:
    """Compare providers.yaml between two refs and return warnings."""
    old_text = _get_file_at_ref(old_ref, "configs/providers.yaml")
    new_text = _get_file_at_ref(new_ref, "configs/providers.yaml")

    if old_text is None or new_text is None:
        return []

    warnings: list[str] = []

    # Check for model → model_env migration
    if "model:" in old_text and "model_env:" in new_text:
        old_has_model = "model:" in old_text and "model_env:" not in old_text
        new_has_model_env = "model_env:" in new_text
        if old_has_model and new_has_model_env:
            warnings.append(
                "  ⚠ Provider configuration changed: 'model' is now read from env var.\n"
                "    Set LLM_MODEL in your .env (e.g. LLM_MODEL=deepseek-v4-flash).\n"
                "    See: paper-compass init --force to regenerate config."
            )

    return warnings


def _detect_breaking_changes(old_ref: str, new_ref: str) -> list[str]:
    """Return a list of user-facing warnings about breaking changes."""
    warnings: list[str] = []
    warnings.extend(_detect_env_var_changes(old_ref, new_ref))
    warnings.extend(_detect_config_schema_changes(old_ref, new_ref))
    return warnings


# ── Changelog ─────────────────────────────────────────────────────────────

def _get_changelog(old_ref: str, new_ref: str) -> str:
    """Return a human-readable list of commits between two refs."""
    result = _git("log", "--oneline", f"{old_ref}..{new_ref}")
    if result.returncode != 0 or not result.stdout.strip():
        return ""
    return result.stdout.strip()


# ── Update execution ──────────────────────────────────────────────────────

def _perform_update(target_ref: str) -> bool:
    """Fetch + checkout target ref, sync the managed runtime. Returns True on success."""
    print(f"\n  Fetching updates from origin...")
    result = _git("fetch", "origin", "--tags")
    if result.returncode != 0:
        print(f"  ✗ git fetch failed: {result.stderr.strip()}")
        return False

    print(f"  Switching to {target_ref}...")
    result = _git("checkout", target_ref)
    if result.returncode != 0:
        result2 = _git("checkout", f"origin/{target_ref}")
        if result2.returncode != 0:
            print(f"  ✗ git checkout failed: {result.stderr.strip()}")
            return False

    print("  Syncing managed runtime (.venv)...")
    try:
        state = ensure_managed_runtime(
            project_root=PROJECT_ROOT,
            bootstrap_python=Path(sys.executable),
            with_dev=(PROJECT_ROOT / "tests").exists(),
        )
    except ManagedRuntimeError as exc:
        print(f"  ✗ managed runtime sync failed:\n{exc}")
        return False

    print(f"  ✓ Managed runtime ready: {state.managed_python}")
    return True


# ── Post-update verification ──────────────────────────────────────────────

def _run_post_checks() -> None:
    """Run paper-compass validate + quick pytest smoke inside the managed runtime."""
    print()

    state = ensure_managed_runtime(
        project_root=PROJECT_ROOT,
        bootstrap_python=Path(sys.executable),
        with_dev=(PROJECT_ROOT / "tests").exists(),
    )
    managed_python = str(state.managed_python)

    result = subprocess.run(
        [managed_python, "-m", "paper_compass.cli.validate"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )
    if result.returncode == 0:
        print("  ✓ paper-compass validate: OK")
    else:
        print("  ✗ paper-compass validate: check failed")
        if result.stdout.strip():
            print(result.stdout.strip())
        print("\n  Try: paper-compass init --force  to reconfigure.")

    if (PROJECT_ROOT / "tests").exists():
        test_result = subprocess.run(
            [managed_python, "-m", "pytest", "tests/", "-x", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        if test_result.returncode == 0:
            print("  ✓ pytest: all tests pass")
        else:
            print("  ⚠ pytest: some tests failed (may be environment-specific)")
            lines = test_result.stdout.strip().splitlines()
            for line in lines[-5:]:
                print(f"    {line}")


# ── Summary output ────────────────────────────────────────────────────────

def _print_summary(
    old_ver: str,
    new_ver: str,
    warnings: list[str],
    changelog: str,
) -> None:
    """Print a human-readable update summary."""
    print()
    print(f"  paper-compass updated: {old_ver} → {new_ver}")
    print()

    if changelog:
        print("  Changes in this update:")
        for line in changelog.splitlines():
            print(f"    {line}")
        print()

    if warnings:
        print("  ⚠ Upgrade notes:")
        for w in warnings:
            print(w)
        print()


# ── Entry for top-level CLI dispatch ──────────────────────────────────────

def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add 'update' subcommand to the top-level paper-compass CLI."""
    parser = subparsers.add_parser(
        "update",
        help="Update paper-compass to the latest version",
        description=(
            "Check for and apply updates from the GitHub repository.\n"
            "Detects breaking changes and guides you through the upgrade."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check for updates, do not apply changes",
    )
    parser.add_argument(
        "--version",
        metavar="VERSION",
        help="Update to a specific version tag (e.g. v1.3.0)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip safety checks (uncommitted changes, etc.)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the update without making changes",
    )
    parser.set_defaults(func=execute_update)


def execute_update(args: argparse.Namespace) -> int:
    """Execute the update subcommand."""
    try:
        return _execute_update_impl(args)
    except RuntimeError as e:
        print(f"\n  ✗ {e}")
        return 1


def _execute_update_impl(args: argparse.Namespace) -> int:
    # 1. Pre-flight checks
    _ensure_git_available()

    current = _get_current_version()
    print(f"\n  Current version: {current}")

    # Fetch tags so we have up-to-date info for --check
    fetch_result = _git("fetch", "origin", "--tags")
    if fetch_result.returncode != 0:
        print(f"  ⚠ Could not fetch from remote (offline?)")
        if not args.check:
            print("  Try again when you have network access.")
            return 1

    target = _get_target_version(args)

    if target == current or (current.startswith(target.lstrip("v"))):
        print(f"  ✓ Already up to date ({target})")
        return 0

    print(f"  Target version:  {target}")

    # --check mode: just report, don't change anything
    if args.check:
        changelog = _get_changelog(current, target)
        if changelog:
            print(f"\n  Available changes ({current} → {target}):")
            for line in changelog.splitlines():
                print(f"    {line}")
        print(f"\n  Run 'paper-compass update' to apply this update.")
        return 0

    # 2. Safety checks (unless --force)
    if not args.dry_run:
        _ensure_clean_worktree(args.force)

    # 3. Breaking change detection
    warnings = _detect_breaking_changes(current, target)

    # 4. Changelog
    changelog = _get_changelog(current, target)

    # 5. Show what will happen
    print()
    print(f"  Updating {current} → {target}")
    if changelog:
        print("\n  Changes:")
        for line in changelog.splitlines():
            print(f"    {line}")

    if warnings:
        print("\n  ⚠ Upgrade notes:")
        for w in warnings:
            print(w)
        print()

    # --dry-run: stop here
    if args.dry_run:
        print("  (dry-run — no changes made)")
        return 0

    # 6. Perform update
    if not _perform_update(target):
        return 1

    # 7. Post-update verification
    _run_post_checks()

    # 8. Summary
    _print_summary(current, target, warnings, "")

    if warnings:
        print("  Review the upgrade notes above for any manual steps needed.")
        print("  If issues persist: paper-compass init --force")
    print()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="paper-compass update")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--version", metavar="VERSION")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(execute_update(args))
