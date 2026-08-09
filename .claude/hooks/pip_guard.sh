#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cmd=$(claude_command)
echo "$cmd" | grep -qE '^pip install|^pip3 install' || exit 0
log_event "pip_guard" 2 "$cmd"
block "Use uv, not pip. Run: uv add <package>"
