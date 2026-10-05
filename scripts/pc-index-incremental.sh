#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

pc_cd_repo_root
CLI_BIN="$(pc_managed_cli)"
pc_require_cmd "$CLI_BIN"

exec "$CLI_BIN" sync "$@"
