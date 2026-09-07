#!/usr/bin/env bash
# Shared helpers for the worktree tooling (scripts/wt-*.sh, tmux-dev.sh).
# Source it; don't execute it. Callers may pre-set ROOT to target another checkout.
WT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "$WT_LIB_DIR/.." && pwd)}"

BASE_BRANCH="${WT_BASE_BRANCH:-dev}"   # what wt-new.sh cuts branches from and wt-land.sh merges into
PROTECTED_BRANCHES="dev main"          # never pushed from a worktree, never checked out in one
# The same list lives in two more places on purpose: git-push-guard.sh (the
# guard must not depend on a file an old branch may lack) and the completion
# filter in wt-go.bash (the union across every repo that has the tooling).
# Change all three.
MAIN_BACKEND_PORT=8000
MAIN_FRONTEND_PORT=5173

die() { echo "wt: $*" >&2; exit 1; }
repo_name() { basename -s .git "$(git -C "$ROOT" config --get remote.origin.url)"; }
main_checkout() { dirname "$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)"; }
in_worktree() { [ "$(git -C "$ROOT" rev-parse --git-dir)" != "$(git -C "$ROOT" rev-parse --git-common-dir)" ]; }
current_branch() { git -C "$ROOT" rev-parse --abbrev-ref HEAD; }
# Branch name -> plain identifier (no slash, no dot), used in generated names.
slug() { printf '%s' "$1" | tr -c 'A-Za-z0-9' '_' | tr 'A-Z' 'a-z'; }
# "<repo>/<branch>" with the characters tmux forbids in session names replaced.
session_name() { printf '%s/%s' "$(repo_name)" "$(printf '%s' "$1" | tr '.:' '--')"; }
# Deterministic ports from the repo and branch names: the same branch always
# gets the same pair, and the suffix matches on both so 18042 <-> 19042 read as
# one worktree. The repo name is in the hash because one machine runs the same
# tooling in several repos, and the same branch name in two of them (this
# branch, in resslab-hub and bluecity-viz, 2026-09-06) must not fight for a pair.
# 500 slots only, so two branches can still hash to the same offset: when
# another worktree's .env.worktree already holds the pair, or something on the
# machine is listening on it (a worktree of another repo, whose files this
# cannot see), step forward until a free one is found. The branch that got there
# first keeps its ports; a re-run on the same worktree keeps its own (it is not
# "another" worktree, and wt-setup.sh reuses the pair it wrote last time anyway).
branch_ports() {
  local branch=$1 h off taken tries=0
  h=$(printf '%s/%s' "$(repo_name)" "$branch" | cksum | cut -d' ' -f1)
  off=$((h % 500))
  taken="$(ports_in_use_by_others "$branch"; listening_ports)"
  while [ "$tries" -lt 500 ] && printf '%s\n' "$taken" | grep -qx "$((18000 + off))"; do
    off=$(((off + 1) % 500)); tries=$((tries + 1))
  done
  BACKEND_PORT=$((18000 + off)); FRONTEND_PORT=$((19000 + off))
}
# Backend ports written in the .env.worktree of every other worktree of this repo.
ports_in_use_by_others() {
  local self=$1 p
  while IFS= read -r p; do
    [ -f "$p/.env.worktree" ] || continue
    [ "$(sed -n 's/^WT_BRANCH=//p' "$p/.env.worktree")" != "$self" ] || continue
    sed -n 's/^BACKEND_PORT=//p' "$p/.env.worktree"
  done < <(git -C "$ROOT" worktree list --porcelain | sed -n 's#^worktree ##p')
}
# TCP ports something is listening on right now (empty where ss is missing or
# the caller runs in a sandbox with its own network namespace).
listening_ports() { ss -Hltn 2>/dev/null | awk '{print $4}' | sed 's/.*://' | sort -u; }
# The keys wt-setup.sh writes to .env.worktree.
ENV_WORKTREE_KEYS="WT_BRANCH WT_SLUG BACKEND_PORT FRONTEND_PORT"
# Export .env.worktree if this checkout has one. Without one (the main checkout)
# drop those keys first: a shell that sourced another worktree's file, or a tmux
# server started from one, would otherwise hand its ports to this checkout, and
# the backend then listens where the frontend does not look.
load_env_worktree() {
  if [ -f "$ROOT/.env.worktree" ]; then set -a; . "$ROOT/.env.worktree"; set +a
  else unset $ENV_WORKTREE_KEYS; fi
  : "${BACKEND_PORT:=$MAIN_BACKEND_PORT}" "${FRONTEND_PORT:=$MAIN_FRONTEND_PORT}"
}
# Path of the worktree that has BRANCH checked out, empty if none.
worktree_path_for() {
  git -C "$ROOT" worktree list --porcelain | awk -v b="refs/heads/$1" '/^worktree /{p=$2} $0=="branch "b{print p}'
}
# Claude's sandbox bind-mounts its deny list over a worktree and leaves the mount
# points behind as 0-byte files and empty dirs (.bashrc, .idea, .claude/hooks,
# backend/.mcp.json, ...). git lists them as untracked, so they block a land or
# a wt-done. Drop them: empty and untracked, nothing is lost (git never keeps an
# empty dir anyway). Run it from the host, inside the sandbox they are mounts.
drop_sandbox_stubs() {
  local wt=$1 f
  while IFS= read -r f; do
    if [ -f "$wt/$f" ] && [ ! -s "$wt/$f" ]; then rm -f "$wt/$f" && echo "dropped sandbox stub $f"; fi
  done < <(git -C "$wt" ls-files --others --exclude-standard)
  find "$wt" -mindepth 1 -maxdepth 3 -type d -empty \
    -not -path "$wt/.git*" -not -path "*/node_modules/*" -not -path "*/.venv/*" -delete 2>/dev/null || true
}
