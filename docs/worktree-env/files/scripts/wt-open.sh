#!/usr/bin/env bash
# Open a checkout's dev server in the browser (and print the URL).
#   scripts/wt-open.sh [frontend|backend] [branch]
# Defaults: the frontend of the checkout you're in. With a branch name it finds
# that branch's worktree and reads its ports from .env.worktree.
set -euo pipefail
SCRIPTS="$(dirname "$(readlink -f "$0")")"
. "$SCRIPTS/wt-lib.sh"
what="${1:-frontend}"; branch="${2:-}"
if [ -n "$branch" ]; then
  path="$(worktree_path_for "$branch")"
  [ -n "$path" ] || die "no worktree has '$branch' checked out (wt list)"
  ROOT="$path"
fi
load_env_worktree
case "$what" in
  frontend|f) url="http://localhost:$FRONTEND_PORT/" ;;
  backend|b|api|docs) url="http://127.0.0.1:$BACKEND_PORT/docs" ;;
  *) die "usage: wt-open.sh [frontend|backend] [branch]" ;;
esac
echo "$url"
command -v xdg-open >/dev/null && xdg-open "$url" >/dev/null 2>&1 || true
