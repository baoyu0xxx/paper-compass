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

pc_can_run_python() {
  local candidate="$1"
  [[ -n "$candidate" ]] || return 1

  if [[ "$candidate" == */* || "$candidate" == *\\* ]]; then
    [[ -x "$candidate" ]] || return 1
  else
    command -v "$candidate" >/dev/null 2>&1 || return 1
  fi

  "$candidate" -c 'import sys' >/dev/null 2>&1
}

pc_default_python() {
  if [[ -n "${PAPER_COMPASS_PYTHON:-}" ]]; then
    pc_can_run_python "${PAPER_COMPASS_PYTHON}" || pc_die "configured PAPER_COMPASS_PYTHON is not runnable: ${PAPER_COMPASS_PYTHON}"
    printf '%s\n' "${PAPER_COMPASS_PYTHON}"
    return
  fi

  local repo_root
  repo_root="$(pc_repo_root)"

  local candidate
  for candidate in \
    "${repo_root}/.venv/bin/python" \
    "${repo_root}/.venv/Scripts/python.exe" \
    python \
    python3
  do
    if pc_can_run_python "$candidate"; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  pc_die "no runnable Python interpreter found (tried ${repo_root}/.venv/bin/python, python, python3)"
}

pc_managed_python() {
  if [[ -n "${PAPER_COMPASS_PYTHON:-}" ]]; then
    pc_can_run_python "${PAPER_COMPASS_PYTHON}" || pc_die "configured PAPER_COMPASS_PYTHON is not runnable: ${PAPER_COMPASS_PYTHON}"
    printf '%s\n' "${PAPER_COMPASS_PYTHON}"
    return
  fi

  local repo_root
  repo_root="$(pc_repo_root)"

  local candidate
  for candidate in \
    "${repo_root}/.venv/bin/python" \
    "${repo_root}/.venv/Scripts/python.exe"
  do
    if pc_can_run_python "$candidate"; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  pc_die "managed runtime is missing; run python scripts/bootstrap_runtime.py from ${repo_root}"
}

pc_can_run_cmd() {
  local candidate="$1"
  [[ -n "$candidate" ]] || return 1

  if [[ "$candidate" == */* || "$candidate" == *\\* ]]; then
    [[ -x "$candidate" ]] || return 1
  else
    command -v "$candidate" >/dev/null 2>&1 || return 1
  fi
}

pc_managed_cli() {
  if [[ -n "${PAPER_COMPASS_CLI:-}" ]]; then
    pc_can_run_cmd "${PAPER_COMPASS_CLI}" || pc_die "configured PAPER_COMPASS_CLI is not runnable: ${PAPER_COMPASS_CLI}"
    printf '%s\n' "${PAPER_COMPASS_CLI}"
    return
  fi

  local repo_root
  repo_root="$(pc_repo_root)"

  local candidate
  for candidate in \
    "${repo_root}/.venv/bin/paper-compass" \
    "${repo_root}/.venv/Scripts/paper-compass.exe" \
    "${repo_root}/.venv/Scripts/paper-compass"
  do
    if pc_can_run_cmd "$candidate"; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  pc_die "managed paper-compass CLI is missing; run python scripts/bootstrap_runtime.py from ${repo_root}"
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
