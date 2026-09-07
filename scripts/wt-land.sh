#!/usr/bin/env bash
# Land a worktree's branch into $BASE_BRANCH (dev) and clean everything up.
#   scripts/wt-land.sh <branch>            rebase onto origin/dev, push, open a PR, squash-merge
#                                          (auto-merge when checks pass), update local dev, remove the worktree
#   scripts/wt-land.sh <branch> --local    rebase, `git merge --no-ff` into dev here, run the CI checks
#                                          (frontend lint + type-check, backend ruff), push dev, remove
#                                          the worktree   (WT_SKIP_CHECKS=1 skips the checks)
# Run it from the main checkout: gh refuses to delete a branch git still has
# checked out in a worktree (cli/cli#13380), and this is the one place allowed to
# push dev (scripts/git-push-guard.sh blocks that from worktrees).
set -euo pipefail
SCRIPTS="$(dirname "$(readlink -f "$0")")"
. "$SCRIPTS/wt-lib.sh"
branch="${1:-}"; mode="${2:-pr}"
[ -n "$branch" ] || die "usage: wt-land.sh <branch> [--local]"
in_worktree && die "run wt-land from the main checkout: $(main_checkout)"
cd "$ROOT"
for p in $PROTECTED_BRANCHES; do [ "$branch" != "$p" ] || die "refusing to land protected branch '$branch'"; done
wt_path="$(worktree_path_for "$branch")"
[ -n "$wt_path" ] || die "no worktree has '$branch' checked out (wt list)"
drop_sandbox_stubs "$wt_path"
[ -z "$(git -C "$wt_path" status --porcelain)" ] || die "$wt_path has uncommitted or untracked changes — commit or clean them first"

git fetch origin
# A branch cut from a newer branch than the base (e.g. main while dev lags) would
# drag every missing commit into its PR. Refuse rather than rebase 200 commits.
# Check the point where the branch left main, not that the branch contains all of
# origin/dev: any commit landed on dev after the branch was cut is normal, the
# rebase below takes care of it.
fork="$(git merge-base "$branch" origin/main)"
git merge-base --is-ancestor "$fork" "origin/$BASE_BRANCH" \
  || die "$branch holds commits of main that origin/$BASE_BRANCH lacks. Fast-forward $BASE_BRANCH first (e.g. git push origin main:$BASE_BRANCH), then re-run"

echo "==> rebasing $branch onto origin/$BASE_BRANCH"
git -C "$wt_path" rebase "origin/$BASE_BRANCH" || die "rebase stopped — resolve it in $wt_path, then re-run"
git -C "$wt_path" push --force-with-lease origin "$branch"

update_local_base() {
  local base_wt; base_wt="$(worktree_path_for "$BASE_BRANCH")"
  if [ -n "$base_wt" ]; then git -C "$base_wt" pull --ff-only origin "$BASE_BRANCH"
  else git fetch origin "$BASE_BRANCH:$BASE_BRANCH"; fi
}
cleanup() {
  wt remove "$branch"                               # fires scripts/wt-teardown.sh via .wt.toml
  git branch -D "$branch" 2>/dev/null || true
  git push origin --delete "$branch" 2>/dev/null || true
  echo "==> landed $branch into $BASE_BRANCH; worktree, local and remote branch removed"
}

case "$mode" in
  pr)
    if ! gh pr view "$branch" --json number -q .number >/dev/null 2>&1; then
      gh pr create --base "$BASE_BRANCH" --head "$branch" --fill
    fi
    # --auto waits for required checks; on a repo without auto-merge enabled it
    # errors, so fall back to an immediate squash-merge.
    gh pr merge "$branch" --squash --auto || gh pr merge "$branch" --squash
    echo "==> waiting for the PR to merge…"
    state=""
    for _ in $(seq 1 90); do
      state="$(gh pr view "$branch" --json state -q .state)"
      [ "$state" = MERGED ] && break
      sleep 20
    done
    [ "$state" = MERGED ] || die "PR still $state after 30 min — re-run wt-land once it merges to finish the cleanup"
    update_local_base
    cleanup
    ;;
  --local)
    [ -z "$(git status --porcelain --untracked-files=no)" ] || die "the main checkout has uncommitted changes"
    [ -z "$(worktree_path_for "$BASE_BRANCH")" ] || die "$BASE_BRANCH is checked out in a worktree — remove it (wt remove $BASE_BRANCH) or land with a PR"
    prev="$(current_branch)"
    git checkout "$BASE_BRANCH"
    git pull --ff-only origin "$BASE_BRANCH"
    git merge --no-ff "$branch" -m "Merge branch '$branch' into $BASE_BRANCH"
    # The root Makefile has no lint/test target: run the frontend checks CI runs,
    # and on the backend the same blocking selection as CI's flake8 step (syntax
    # errors and undefined names) through ruff, the only linter in its deps.
    # --no-fix: pyproject turns fixes on, and a land must not edit files.
    if [ "${WT_SKIP_CHECKS:-0}" != 1 ]; then
      (cd frontend && pnpm run lint && pnpm run type-check)
      (cd backend && uv run ruff check --no-fix --select E9,F63,F7,F82 app)
    fi
    git push origin "$BASE_BRANCH"
    git checkout "$prev"
    cleanup
    ;;
  *) die "usage: wt-land.sh <branch> [--local]" ;;
esac
