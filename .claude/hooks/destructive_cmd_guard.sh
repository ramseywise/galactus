#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cmd=$(claude_command)
# Match the stripped text so prose that merely names a destructive command in a heredoc
# body does not trip the guard; log the command as written.
strip_heredoc_bodies "$cmd" | grep -qE 'rm -rf /|rm -rf ~|DROP TABLE|TRUNCATE TABLE' || exit 0
log_event "destructive_cmd_guard" 2 "$cmd"
block "Blocked: destructive command."
