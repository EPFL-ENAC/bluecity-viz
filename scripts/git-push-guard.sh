#!/usr/bin/env bash
# pre-push guard, installed by scripts/wt-setup.sh in the shared hooks directory
# (git feeds the refs it is about to push on stdin). Inside a git worktree a push
# may only update that worktree's own branch, and never dev/main. The main
# checkout is unrestricted: that's where scripts/wt-land.sh lands branches.
# Claude's own deny rules cover the same pushes, but this runs in git itself, so
# it holds for any process in the worktree and can't be talked around.
# The branch list is duplicated from wt-lib.sh on purpose: the guard must not
# depend on a file that could be missing in an old branch. Change both (and the
# completion filter in wt-go.bash).
set -euo pipefail
[ "$(git rev-parse --git-dir)" != "$(git rev-parse --git-common-dir)" ] || exit 0   # main checkout
PROTECTED="dev main"
branch="$(git rev-parse --abbrev-ref HEAD)"
refuse() { echo "push-guard: $*" >&2; echo "push-guard: land branches from the main checkout with scripts/wt-land.sh" >&2; exit 1; }
saw_ref=0
while read -r _local_ref _local_sha remote_ref _remote_sha; do
  [ -n "${remote_ref:-}" ] || continue
  saw_ref=1
  target="${remote_ref#refs/heads/}"
  for p in $PROTECTED; do [ "$target" != "$p" ] || refuse "a worktree never pushes protected branch '$p'"; done
  [ "$target" = "$branch" ] || refuse "worktree on '$branch' may only push '$branch', not '$target'"
done
# No ref lines on stdin (unexpected hook runner): still keep protected branches safe.
if [ "$saw_ref" = 0 ]; then
  for p in $PROTECTED; do [ "$branch" != "$p" ] || refuse "a worktree never pushes protected branch '$p'"; done
fi
