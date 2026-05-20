#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

pc_cd_repo_root
PYTHON_BIN="$(pc_default_python)"
pc_require_cmd "$PYTHON_BIN"

exec "$PYTHON_BIN" scripts/build_index.py \
  --library "$(pc_default_library_path)" \
  --db-path "$(pc_default_db_path)" \
  --incremental \
  --prune-deleted \
  "$@"
