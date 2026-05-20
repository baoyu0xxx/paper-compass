#!/usr/bin/env bash

set -euo pipefail

pc_die() {
  echo "[paper-compass] ERROR: $*" >&2
  exit 1
}

pc_repo_root() {
  if [[ -n "${PAPER_COMPASS_ROOT:-}" ]]; then
    [[ -d "${PAPER_COMPASS_ROOT}" ]] || pc_die "PAPER_COMPASS_ROOT does not exist: ${PAPER_COMPASS_ROOT}"
    printf '%s\n' "${PAPER_COMPASS_ROOT}"
    return
  fi

  local common_dir
  common_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  printf '%s\n' "$(cd -- "${common_dir}/../.." && pwd)"
}

pc_cd_repo_root() {
  cd -- "$(pc_repo_root)"
}

pc_require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || pc_die "required command not found: $cmd"
}

pc_default_python() {
  if [[ -n "${PAPER_COMPASS_PYTHON:-}" ]]; then
    printf '%s\n' "${PAPER_COMPASS_PYTHON}"
    return
  fi
  printf '%s\n' "python3"
}

pc_default_library_path() {
  printf '%s\n' "${PAPER_COMPASS_LIBRARY_PATH:-data/zotero-export/library.json}"
}

pc_default_db_path() {
  printf '%s\n' "${PAPER_COMPASS_DB_PATH:-data/vectordb}"
}

pc_default_text_dir() {
  printf '%s\n' "${PAPER_COMPASS_TEXT_DIR:-data/texts}"
}

pc_default_wiki_root() {
  printf '%s\n' "${PAPER_COMPASS_WIKI_ROOT:-./wiki}"
}

pc_default_logs_dir() {
  printf '%s\n' "${PAPER_COMPASS_LOG_DIR:-data/logs}"
}
