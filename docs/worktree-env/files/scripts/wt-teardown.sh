#!/usr/bin/env bash
# Tear a worktree's runtime down (wt calls it from pre_remove): its tmux session,
# anything still bound to its ports, and its branch database if one was cloned.
# Safe to run twice; never touches the main checkout's servers.
set -uo pipefail
ROOT="${WT_PATH:-$(git rev-parse --show-toplevel)}"
SCRIPTS="$(dirname "$(readlink -f "$0")")"
. "$SCRIPTS/wt-lib.sh"
BRANCH="${WT_BRANCH:-$(current_branch)}"
SESSION="$(session_name "$BRANCH")"

tmux kill-session -t "=$SESSION" 2>/dev/null && echo "killed tmux session $SESSION"

# Only a worktree has .env.worktree; without it BACKEND_PORT would fall back to
# 8000 and we'd kill the main checkout's server.
if [ -f "$ROOT/.env.worktree" ]; then
  load_env_worktree
  for p in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    fuser -k -n tcp "$p" >/dev/null 2>&1 && echo "freed port $p"
  done
  if [ "${DB_NAME:-$SHARED_DB}" != "$SHARED_DB" ]; then
    ROOT="$ROOT" "$SCRIPTS/wt-db.sh" drop || echo "wt-teardown: could not drop $DB_NAME (drop it by hand: make db-branch-drop)" >&2
  fi
fi
exit 0
