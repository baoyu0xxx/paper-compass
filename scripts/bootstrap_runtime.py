#!/usr/bin/env python3
"""Bootstrap or refresh the repo-local paper-compass managed runtime."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paper_compass.runtime_env import ManagedRuntimeError, ensure_managed_runtime


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the repo-local paper-compass runtime")
    parser.add_argument("--python", help="Bootstrap interpreter to use when creating .venv")
    parser.add_argument(
        "--without-dev",
        action="store_true",
        help="Install only runtime dependencies (skip dev extras)",
    )
    args = parser.parse_args()

    try:
        state = ensure_managed_runtime(
            project_root=PROJECT_ROOT,
            bootstrap_python=Path(args.python) if args.python else None,
            with_dev=not args.without_dev,
        )
    except ManagedRuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"managed runtime ready: {state.managed_python}")
    print("next steps:")
    print("  - paper-compass init")
    print("  - paper-compass validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
