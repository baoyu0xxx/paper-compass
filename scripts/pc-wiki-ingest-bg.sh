#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

pc_cd_repo_root
PYTHON_BIN="$(pc_default_python)"
pc_require_cmd "$PYTHON_BIN"

LOG_DIR="$(pc_default_logs_dir)"
LOG_FILE="${LOG_DIR}/wiki_gen.log"
mkdir -p "$LOG_DIR"

nohup "$PYTHON_BIN" scripts/ingest_to_wiki.py \
  --library "$(pc_default_library_path)" \
  --wiki-root "$(pc_default_wiki_root)" \
  --skip-existing \
  --workers "${PAPER_COMPASS_WIKI_WORKERS:-10}" \
  "$@" >"$LOG_FILE" 2>&1 &

PID=$!
printf 'wiki background job started\n'
printf 'pid: %s\n' "$PID"
printf 'log: %s\n' "$LOG_FILE"
printf 'tail: tail -f %s\n' "$LOG_FILE"
printf 'ps: ps -p %s -o pid,etime,cmd\n' "$PID"
printf 'note: safe to rerun; --skip-existing lets it resume incrementally.\n'
