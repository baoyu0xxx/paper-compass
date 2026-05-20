#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

pc_cd_repo_root

if command -v paper-compass-mcp >/dev/null 2>&1; then
  if paper-compass-mcp --help >/dev/null 2>&1; then
    exec paper-compass-mcp --mcp "$@"
  fi
  echo "[paper-compass] WARN: installed paper-compass-mcp entrypoint is unavailable; falling back to scripts/run_mcp_server.py" >&2
fi

PYTHON_BIN="$(pc_default_python)"
pc_require_cmd "$PYTHON_BIN"
exec "$PYTHON_BIN" scripts/run_mcp_server.py --mcp "$@"
