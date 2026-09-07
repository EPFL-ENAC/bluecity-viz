#!/usr/bin/env bash
# Create the six perf worktrees from origin/dev and fire each brief in its claude pane.
#
#   docs/briefs/launch.sh            # all six, detached (attach later with: make go BRANCH=...)
#   docs/briefs/launch.sh s1 s4      # only some
#
# Works from anywhere: the briefs are read next to this script, the worktrees are created
# from the MAIN checkout (found through the shared .git dir). Each worktree installs its own
# frontend node_modules and backend .venv, so expect a few minutes and a few GB.
set -euo pipefail

BRIEFS="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$(git -C "$BRIEFS" rev-parse --path-format=absolute --git-common-dir)/.." && pwd)"
cd "$ROOT"
echo "main checkout: $ROOT"

# --- preconditions (see README.md) ---------------------------------------------
git fetch origin --quiet
if ! git merge-base --is-ancestor 100b7c2 origin/dev 2>/dev/null; then
  echo "origin/dev does not contain 100b7c2 (Workbench redesign), the briefs quote its line numbers." >&2; exit 1
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "working tree is dirty; commit or drop the changes first (wt-land refuses dirty trees)" >&2
  git status --short --untracked-files=no >&2; exit 1
fi
# node_modules and the venv are hardlinked from the pnpm / uv stores; keep 1.2 GB per worktree as margin
free_gb=$(df -BG --output=avail "$ROOT" | tail -1 | tr -dc '0-9')
n=${#@}; [ "$n" -gt 0 ] || n=6; need_gb=$(( (12 * n + 9) / 10 ))
if [ "$free_gb" -lt "$need_gb" ]; then
  echo "only ${free_gb} GB free on $(df --output=target "$ROOT" | tail -1); need about ${need_gb} GB." >&2
  echo "free space first (uv cache prune, npm cache clean --force, flatpak uninstall --unused) or move caches to /mnt/data." >&2
  exit 1
fi
if ! (cd backend && uv run ruff format --check app >/dev/null 2>&1 && uv run ruff check --no-fix app >/dev/null 2>&1); then
  echo "warning: backend is not ruff-clean on dev. Commit 'chore(backend): ruff format' on dev first," >&2
  echo "         or S4 and S6 will both reformat every file and conflict. Continuing anyway." >&2
fi

# --- sessions -----------------------------------------------------------------
declare -A BRANCH=(
  [s1]=perf/state-persistence
  [s2]=perf/deck-rendering
  [s3]=perf/maplibre-layers
  [s4]=perf/backend-routing
  [s5]=chore/frontend-tooling
  [s6]=fix/backend-cvrp-quality
  [s7]=feat/od-pairs-ui
  [final]=chore/tooling-upgrades
)
declare -A FILE=(
  [s1]=s1-state-persistence.md
  [s2]=s2-deck-rendering.md
  [s3]=s3-maplibre-layers.md
  [s4]=s4-backend-routing.md
  [s5]=s5-frontend-tooling.md
  [s6]=s6-backend-cvrp-quality.md
  [s7]=s7-od-pairs-ui.md
  [final]=final-tooling-upgrades.md
)

# "s7" and "final" are not started by default: they run after the six others are landed
# (docs/briefs/launch.sh s7 final).
sessions=("$@")
[ ${#sessions[@]} -gt 0 ] || sessions=(s5 s6 s4 s1 s2 s3)

for s in "${sessions[@]}"; do
  b="${BRANCH[$s]:-}"; f="${FILE[$s]:-}"
  [ -n "$b" ] || { echo "unknown session: $s (use s1..s7 or final)" >&2; exit 1; }
  echo "==> $s  $b  ($f)"
  scripts/wt-new.sh "$b" origin/dev --prompt "$BRIEFS/$f" --no-attach
done

echo
echo "All sessions started detached. Attach with:  make go BRANCH=<branch>"
echo "Landing order: s5, s6, s4, s1, s2, s3, then final (docs/briefs/README.md)."
