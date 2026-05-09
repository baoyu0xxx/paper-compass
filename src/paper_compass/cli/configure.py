"""paper-compass init / configure subcommand.

Supports two modes:
1. Interactive (default): prompts user for LLM + embedding config step by step
2. Non-interactive: --llm-args and --embed-args in lm-eval key=value style

Writes .env file with the chosen configuration.
API keys support $ENV_VAR_NAME syntax for runtime resolution.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from paper_compass.cli.arg_utils import MergeDictAction
from paper_compass.env_utils import PROJECT_ROOT, DEFAULT_ENV_PATH

# ── Default values ──────────────────────────────────────────────────────────

DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o"
DEFAULT_EMBED_BASE_URL = "https://api.openai.com/v1"
DEFAULT_EMBED_MODEL = "text-embedding-3-small"

DEFAULT_VOLC_EMBED_BASE_URL = (
    "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
)
DEFAULT_VOLC_EMBED_MODEL = "ep-20260420154519-9w64q"  # doubao-embedding-vision-250615


# ── Interactive prompts ────────────────────────────────────────────────────


def _available_disciplines() -> list[str]:
    """Discover installed discipline presets under prompts/disciplines/."""
    disciplines_dir = Path("prompts/disciplines")
    if not disciplines_dir.exists() or not disciplines_dir.is_dir():
        return []
    result = []
    try:
        for d in sorted(disciplines_dir.iterdir()):
            if d.is_dir() and (d / "wiki_overview.md").exists():
                result.append(d.name)
    except OSError:
        pass
    return result


def _prompt(
    label: str, default: str = "", env_hint: str = ""
) -> str:
    """Prompt the user for input with an optional default and env hint."""
    if default:
        if env_hint:
            prompt_text = f"  {label} [{env_hint}]: "
        else:
            prompt_text = f"  {label} [{default}]: "
    else:
        prompt_text = f"  {label}: "
    try:
        raw = input(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    if not raw and default:
        return default
    return raw


def _resolve_env_var_hint(key: str) -> str:
    """Suggest a default env var name for a given config key."""
    hints = {
        "LLM_BASE_URL": "https://api.openai.com/v1",
        "EMBED_BASE_URL": "https://api.openai.com/v1",
        "LLM_API_KEY": "$OPENAI_API_KEY",
        "EMBED_API_KEY": "$OPENAI_API_KEY",
        "VOLC_EMBED_API_KEY": "$VOLC_API_KEY",
        "LLM_MODEL": DEFAULT_LLM_MODEL,
        "EMBED_MODEL": DEFAULT_EMBED_MODEL,
        "VOLC_EMBED_MODEL": DEFAULT_VOLC_EMBED_MODEL,
    }
    return hints.get(key, "")


def _interactive_llm() -> dict[str, str]:
    """Interactive step: configure LLM for wiki generation."""
    print()
    print("  ┌─ Step 1: LLM (Wiki Generation) ──────────────────────────────┐")
    print()

    base_url = _prompt("Base URL", DEFAULT_LLM_BASE_URL)
    api_key = _prompt("API key (or $ENV_VAR name)", "", "$OPENAI_API_KEY")
    model = _prompt("Model", DEFAULT_LLM_MODEL)

    print("  └──────────────────────────────────────────────────────────────┘")
    print()

    return {"LLM_BASE_URL": base_url, "LLM_API_KEY": api_key, "LLM_MODEL": model}


def _interactive_embedding() -> dict[str, str]:
    """Interactive step: configure embedding provider."""
    print("  ┌─ Step 2: Embedding ──────────────────────────────────────────┐")
    print("  API style:")
    print("    1) OpenAI-compatible  (standard text-embedding API)")
    print("    2) Volcengine         (doubao-embedding-vision, multimodal)")
    style = _prompt("Choose [1]", "1")

    if style.strip() == "2":
        return _interactive_volcengine_embedding()
    return _interactive_openai_embedding()


def _interactive_openai_embedding() -> dict[str, str]:
    """OpenAI-compatible embedding configuration."""
    base_url = _prompt("Base URL", DEFAULT_EMBED_BASE_URL)
    api_key = _prompt("API key (or $ENV_VAR name)", "", "$OPENAI_API_KEY")
    model = _prompt("Model", DEFAULT_EMBED_MODEL)

    print("  └──────────────────────────────────────────────────────────────┘")
    print()

    return {
        "EMBED_BASE_URL": base_url,
        "EMBED_API_KEY": api_key,
        "EMBED_MODEL": model,
    }


def _interactive_volcengine_embedding() -> dict[str, str]:
    """Volcengine multimodal embedding configuration."""
    base_url = _prompt("Base URL", DEFAULT_VOLC_EMBED_BASE_URL)
    api_key = _prompt("API key (or $ENV_VAR name)", "", "$VOLC_API_KEY")
    model = _prompt("Endpoint ID", DEFAULT_VOLC_EMBED_MODEL)

    print("  └──────────────────────────────────────────────────────────────┘")
    print()

    return {
        "VOLC_EMBED_BASE_URL": base_url,
        "VOLC_EMBED_API_KEY": api_key,
        "VOLC_EMBED_MODEL": model,
    }


def _interactive_wiki_prompt() -> str:
    """Interactive step: configure wiki prompt style."""
    disciplines = _available_disciplines()
    print("  ┌─ Step 3: Wiki Prompt Style ────────────────────────────────────┐")
    print()
    print("  Wiki prompts control how LLMs generate structured knowledge")
    print("  pages from your papers. Choose a prompt style:")
    print()
    print("    1) Default (通用) — General-purpose academic prompts,")
    print("       suitable for any discipline")
    if disciplines:
        for i, d in enumerate(disciplines, 2):
            label = _DISCIPLINE_LABELS.get(d, d.capitalize())
            print(f"    {i}) Preset: {label} — Specialized prompts for {d}")
    print(f"    {len(disciplines) + 2}) Custom path — Use your own prompt files")
    print()

    max_opt = len(disciplines) + 2
    choice = _prompt(f"Choose [1]", "1")

    try:
        idx = int(choice)
    except ValueError:
        # Treat as custom path
        return choice.strip()

    if idx == 1:
        return "default"
    elif 2 <= idx <= len(disciplines) + 1:
        return disciplines[idx - 2]
    elif idx == len(disciplines) + 2:
        custom = input("  Custom prompt directory path: ").strip()
        if not custom:
            print("  No path entered — using default.")
            return "default"
        return custom
    else:
        print(f"  Invalid choice '{choice}' — using default.")
        return "default"


# Human-readable labels for discipline presets
_DISCIPLINE_LABELS: dict[str, str] = {
    "economics": "经济学",
}


# ── .env writer ────────────────────────────────────────────────────────────


def _format_env_value(value: str) -> str:
    """Format a value for .env output.

    Preserve $ENV_VAR references as-is (no quoting needed for .env files).
    """
    return value


def _write_dotenv(
    env_path: str,
    llm_config: dict[str, str],
    embed_config: dict[str, str],
    wiki_prompt: str = "",
    force: bool = False,
) -> None:
    """Write the .env file with the given configuration.

    Preserves any non-conflicting existing lines in the file.
    """
    path = Path(env_path)

    # Read existing env file
    existing_lines: list[str] = []
    existing_keys: dict[str, int] = {}  # key -> line index
    if path.exists() and not force:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                existing_keys[key] = i
            existing_lines.append(line)

    # Build new env content
    all_config = {}
    all_config.update(llm_config)
    all_config.update(embed_config)

    # Determine which keys to write
    if force or not path.exists():
        # Full rewrite
        lines = [
            "# paper-compass configuration (generated by `paper-compass init`)",
            "# API keys support $ENV_VAR syntax: $OPENAI_API_KEY",
            "#",
        ]
        if llm_config:
            lines.extend([
                "# ── LLM (wiki generation) ──────────────────────────────────────",
                _fmt("LLM_BASE_URL", llm_config.get("LLM_BASE_URL", "")),
                _fmt("LLM_API_KEY", llm_config.get("LLM_API_KEY", "")),
                _fmt("LLM_MODEL", llm_config.get("LLM_MODEL", "")),
                "#",
            ])
        if embed_config:
            is_volc = "VOLC_EMBED_BASE_URL" in embed_config
            if is_volc:
                lines.extend([
                    "# ── Embedding (Volcengine) ─────────────────────────────────",
                    _fmt("VOLC_EMBED_BASE_URL", embed_config.get("VOLC_EMBED_BASE_URL", "")),
                    _fmt("VOLC_EMBED_API_KEY", embed_config.get("VOLC_EMBED_API_KEY", "")),
                    _fmt("VOLC_EMBED_MODEL", embed_config.get("VOLC_EMBED_MODEL", "")),
                ])
            else:
                lines.extend([
                    "# ── Embedding (OpenAI-compatible) ──────────────────────────",
                    _fmt("EMBED_BASE_URL", embed_config.get("EMBED_BASE_URL", "")),
                    _fmt("EMBED_API_KEY", embed_config.get("EMBED_API_KEY", "")),
                    _fmt("EMBED_MODEL", embed_config.get("EMBED_MODEL", "")),
                ])
        if wiki_prompt:
            lines.extend([
                "#",
                "# ── Wiki prompt style ───────────────────────────────────────────",
                "# default = general academic; economics = economics preset;",
                "# or a custom path to your own prompt directory",
                _fmt("WIKI_PROMPT", wiki_prompt),
            ])
    else:
        # Merge into existing file
        lines = list(existing_lines)
        all_config["WIKI_PROMPT"] = wiki_prompt
        for key, value in all_config.items():
            if key in existing_keys:
                # Update existing line
                idx = existing_keys[key]
                lines[idx] = f"{key}={_format_env_value(value)}"
            elif value:
                # Append new key
                lines.append(f"{key}={_format_env_value(value)}")
                existing_keys[key] = len(lines) - 1
        # Also add any keys not in all_config that are already in the file

    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ Written to {path}")


def _fmt(key: str, value: str) -> str:
    return f"{key}={_format_env_value(value)}"


# ── Non-interactive: parse --llm-args / --embed-args ──────────────────────


def _llm_args_to_env(llm_args: dict[str, Any]) -> dict[str, str]:
    """Convert --llm-args dict to .env key-value pairs.

    Accepted keys: base_url, api_key, model
    Maps to: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
    """
    env = {}
    if "base_url" in llm_args:
        env["LLM_BASE_URL"] = str(llm_args["base_url"])
    if "api_key" in llm_args:
        env["LLM_API_KEY"] = str(llm_args["api_key"])
    if "model" in llm_args:
        env["LLM_MODEL"] = str(llm_args["model"])
    return env


def _embed_args_to_env(embed_args: dict[str, Any]) -> dict[str, str]:
    """Convert --embed-args dict to .env key-value pairs.

    Accepted keys: api_style (openai|volcengine), base_url, api_key, model
    Maps to:
      OpenAI: EMBED_BASE_URL, EMBED_API_KEY, EMBED_MODEL
      Volcengine: VOLC_EMBED_BASE_URL, VOLC_EMBED_API_KEY, VOLC_EMBED_MODEL
    """
    env = {}
    api_style = str(embed_args.get("api_style", "openai")).lower().strip()

    if api_style == "volcengine":
        prefix = "VOLC_EMBED"
    else:
        prefix = "EMBED"

    if "base_url" in embed_args:
        env[f"{prefix}_BASE_URL"] = str(embed_args["base_url"])
    if "api_key" in embed_args:
        env[f"{prefix}_API_KEY"] = str(embed_args["api_key"])
    if "model" in embed_args:
        env[f"{prefix}_MODEL"] = str(embed_args["model"])

    return env


# ── Build .env from scratch (no interactive, from existing env) ──────────


def _build_config_from_env() -> tuple[dict[str, str], dict[str, str]]:
    """Build LLM + embedding config from existing environment variables.
    
    Used when the user runs 'init' without args but env is already set.
    """
    llm = {}
    if os.environ.get("LLM_BASE_URL"):
        llm["LLM_BASE_URL"] = os.environ["LLM_BASE_URL"]
    if os.environ.get("LLM_API_KEY"):
        llm["LLM_API_KEY"] = os.environ["LLM_API_KEY"]
    if os.environ.get("LLM_MODEL"):
        llm["LLM_MODEL"] = os.environ["LLM_MODEL"]

    embed = {}
    # Prefer OpenAI-style embed config
    if os.environ.get("EMBED_BASE_URL") or os.environ.get("EMBED_API_KEY"):
        if os.environ.get("EMBED_BASE_URL"):
            embed["EMBED_BASE_URL"] = os.environ["EMBED_BASE_URL"]
        if os.environ.get("EMBED_API_KEY"):
            embed["EMBED_API_KEY"] = os.environ["EMBED_API_KEY"]
        if os.environ.get("EMBED_MODEL"):
            embed["EMBED_MODEL"] = os.environ["EMBED_MODEL"]
    elif os.environ.get("VOLC_EMBED_BASE_URL") or os.environ.get("VOLC_EMBED_API_KEY"):
        if os.environ.get("VOLC_EMBED_BASE_URL"):
            embed["VOLC_EMBED_BASE_URL"] = os.environ["VOLC_EMBED_BASE_URL"]
        if os.environ.get("VOLC_EMBED_API_KEY"):
            embed["VOLC_EMBED_API_KEY"] = os.environ["VOLC_EMBED_API_KEY"]
        if os.environ.get("VOLC_EMBED_MODEL"):
            embed["VOLC_EMBED_MODEL"] = os.environ["VOLC_EMBED_MODEL"]

    return llm, embed


# ── Entry for top-level CLI dispatch ────────────────────────────────────


def add_subcommand_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add 'init' subcommand to the top-level paper-compass CLI."""
    parser = subparsers.add_parser(
        "init",
        help="Configure LLM and embedding providers",
        description="Set up LLM and embedding provider configuration for paper-compass.",
        epilog=(
            "Examples:\n"
            "  paper-compass init                    Interactive setup\n"
            "  paper-compass init --force            Overwrite .env\n"
            "  paper-compass init \\\n"
            "    --llm-args base_url=...,model=...   Non-interactive LLM\n"
            "    --embed-args api_style=volcengine,base_url=...,model=..."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--llm-args",
        default=None,
        nargs="+",
        action=MergeDictAction,
        metavar="<arg>",
        help=(
            "LLM configuration as 'key=val,key2=val2' or `key=val` `key2=val2`. "
            "Accepted keys: base_url, api_key, model"
        ),
    )
    parser.add_argument(
        "--embed-args",
        default=None,
        nargs="+",
        action=MergeDictAction,
        metavar="<arg>",
        help=(
            "Embedding configuration as 'key=val,key2=val2'. "
            "Accepted keys: api_style (openai|volcengine), base_url, api_key, model"
        ),
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        default=False,
        help="Overwrite existing .env without confirmation",
    )
    parser.add_argument(
        "--env-path",
        default=str(DEFAULT_ENV_PATH),
        help=f"Path to .env file (default: {DEFAULT_ENV_PATH})",
    )
    parser.add_argument(
        "--wiki-prompt",
        default=None,
        metavar="<style>",
        help=(
            "Wiki prompt style: 'default' (general academic), "
            "'economics' (economics preset), or a path to custom prompts"
        ),
    )

    parser.set_defaults(func=execute_init)


def execute_init(args: argparse.Namespace) -> int:
    """Execute the init/configure subcommand."""
    env_path = args.env_path
    has_env_file = Path(env_path).exists()

    # Non-interactive mode: --llm-args or --embed-args or --wiki-prompt provided
    has_llm_args = bool(args.llm_args)
    has_embed_args = bool(args.embed_args)
    has_wiki_prompt = args.wiki_prompt is not None

    if has_llm_args or has_embed_args or has_wiki_prompt:
        llm_config = _llm_args_to_env(args.llm_args or {})
        embed_config = _embed_args_to_env(args.embed_args or {})
        wiki_prompt = args.wiki_prompt or ""
        _write_dotenv(env_path, llm_config, embed_config, wiki_prompt, force=args.force)
        print()
        print("  ✓ paper-compass configured (non-interactive mode)")
        return 0

    # Check if already configured
    if has_env_file and not args.force:
        content = Path(env_path).read_text(encoding="utf-8")
        has_llm = "LLM_BASE_URL" in content and "LLM_API_KEY" in content
        has_embed = (
            ("EMBED_BASE_URL" in content and "EMBED_API_KEY" in content)
            or ("VOLC_EMBED_BASE_URL" in content and "VOLC_EMBED_API_KEY" in content)
        )
        if has_llm and has_embed:
            print(f"  .env already configured at {env_path}")
            resp = input("  Overwrite? [y/N] ").strip().lower()
            if resp != "y" and resp != "yes":
                print("  Aborted.")
                return 0

    # Check if env vars are already set in shell (e.g. from .bashrc / .zshrc / CI)
    if not args.force:
        llm_from_env, embed_from_env = _build_config_from_env()
        has_llm_env = bool(llm_from_env.get("LLM_BASE_URL") and llm_from_env.get("LLM_API_KEY"))
        has_embed_env = bool(
            (embed_from_env.get("EMBED_BASE_URL") and embed_from_env.get("EMBED_API_KEY"))
            or (embed_from_env.get("VOLC_EMBED_BASE_URL") and embed_from_env.get("VOLC_EMBED_API_KEY"))
        )
        if has_llm_env and has_embed_env:
            wiki_from_env = os.environ.get("WIKI_PROMPT", "")
            print("  ✓ Detected LLM and embedding configuration from shell environment variables")
            _write_dotenv(env_path, llm_from_env, embed_from_env, wiki_from_env, force=True)
            print("  ✓ paper-compass configured from environment variables")
            print("  Run `paper-compass validate` to test connectivity.")
            print()
            return 0

    # Interactive mode
    print()
    print("  ╔═══════════════════════════════════════════════════════════╗")
    print("  ║   paper-compass initial configuration                     ║")
    print("  ║   API keys support $ENV_VAR syntax (e.g. $OPENAI_API_KEY) ║")
    print("  ╚═══════════════════════════════════════════════════════════╝")

    llm_config = _interactive_llm()
    embed_config = _interactive_embedding()
    wiki_prompt = _interactive_wiki_prompt()

    _write_dotenv(env_path, llm_config, embed_config, wiki_prompt, force=True)
    print()
    print("  ✓ paper-compass configured!")
    print("  Run `paper-compass validate` to test connectivity.")
    print()

    return 0


if __name__ == "__main__":
    # Direct invocation (for testing)
    import sys
    parser = argparse.ArgumentParser(prog="paper-compass init")
    parser.add_argument("--llm-args", default=None, nargs="+", action=MergeDictAction, metavar="<arg>")
    parser.add_argument("--embed-args", default=None, nargs="+", action=MergeDictAction, metavar="<arg>")
    parser.add_argument("--force", "-f", action="store_true", default=False)
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--wiki-prompt", default=None, metavar="<style>")
    args = parser.parse_args(args_list if args_list is not None else sys.argv[1:])
    sys.exit(execute_init(args))
