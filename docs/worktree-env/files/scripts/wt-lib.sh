#!/usr/bin/env bash
# Shared helpers for the worktree tooling (scripts/wt-*.sh, tmux-dev.sh).
# Source it; don't execute it. Callers may pre-set ROOT to target another checkout.
WT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$WT_LIB_DIR/.." && pwd)}"

BASE_BRANCH="${WT_BASE_BRANCH:-dev}"   # what scripts/wt-land.sh merges into
PROTECTED_BRANCHES="dev stage main"    # never pushed from a worktree
DB_CONTAINER="${DB_CONTAINER:-resslab-hub-database-1}"
SHARED_DB="postgres"                   # the full 3.4 GB dev dataset (read-only habits apply)
TEMPLATE_DB="resslab_hub_template"     # idle copy of SHARED_DB for branches that need real data volumes
LIGHT_TEMPLATE_DB="resslab_hub_light"  # ~20 MB build from the data repo: main CSVs + 1 series file per type
MAIN_BACKEND_PORT=8000
MAIN_FRONTEND_PORT=5173

die() { echo "wt: $*" >&2; exit 1; }
repo_name() { basename -s .git "$(git -C "$ROOT" config --get remote.origin.url)"; }
main_checkout() { dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)"; }
in_worktree() { [ "$(git -C "$ROOT" rev-parse --git-dir)" != "$(git -C "$ROOT" rev-parse --git-common-dir)" ]; }
current_branch() { git -C "$ROOT" rev-parse --abbrev-ref HEAD; }
# Branch name -> identifier safe for a Postgres database name.
slug() { printf '%s' "$1" | tr -c 'A-Za-z0-9' '_' | tr 'A-Z' 'a-z'; }
# "<repo>/<branch>" with the characters tmux forbids in session names replaced.
session_name() { printf '%s/%s' "$(repo_name)" "$(printf '%s' "$1" | tr '.:' '--')"; }
# Deterministic ports from the branch name: the same branch always gets the same pair,
# and the suffix matches on both so 18042 <-> 19042 read as one worktree.
branch_ports() {
  local h; h=$(printf '%s' "$1" | cksum | cut -d' ' -f1)
  BACKEND_PORT=$((18000 + h % 500)); FRONTEND_PORT=$((19000 + h % 500))
}
# Export .env.worktree if this checkout has one; the main checkout uses the classic ports.
load_env_worktree() {
  if [ -f "$ROOT/.env.worktree" ]; then set -a; . "$ROOT/.env.worktree"; set +a; fi
  : "${BACKEND_PORT:=$MAIN_BACKEND_PORT}" "${FRONTEND_PORT:=$MAIN_FRONTEND_PORT}"
}
psql_db() { docker exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U postgres -q "$@"; }
# set_env_var FILE KEY VALUE — replace KEY=... in place, or append it.
set_env_var() {
  local file=$1 key=$2 value=$3
  if grep -qE "^${key}=" "$file" 2>/dev/null; then sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else printf '%s=%s\n' "$key" "$value" >> "$file"; fi
}
# Path of the worktree that has BRANCH checked out, empty if none.
worktree_path_for() {
  git -C "$ROOT" worktree list --porcelain | awk -v b="refs/heads/$1" '/^worktree /{p=$2} $0=="branch "b{print p}'
}
