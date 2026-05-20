#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

pc_cd_repo_root
PYTHON_BIN="$(pc_default_python)"
pc_require_cmd "$PYTHON_BIN"

exec "$PYTHON_BIN" scripts/ingest_to_wiki.py \
  --library "$(pc_default_library_path)" \
  --wiki-root "$(pc_default_wiki_root)" \
  --skip-existing \
  --workers "${PAPER_COMPASS_WIKI_WORKERS:-10}" \
  "$@"
