#!/usr/bin/env bash
# Close a branch's dev environment once its PR is up: kill the tmux session and
# remove the worktree. `wt remove` fires scripts/wt-teardown.sh on the way out
# (session, ports, branch database). The branch itself stays, local and remote,
# so the work is one `wtgo <branch>` away if it is ever needed again; wt-land
# is the command that also deletes the branch, after merging it.
#   scripts/wt-done.sh <branch> [--force]
#   (or: wtdone <branch> with completion, make wt-done BRANCH=feat/x, or the
#   prefix+X menu inside a session, bound by tmux-dev.sh)
# --force removes a worktree with uncommitted changes. Those changes are lost.
# --path <dir> resolves the branch from a checkout path instead (what the
#   prefix+X menu passes: a key binding knows the pane's path, not the branch).
set -euo pipefail
SCRIPTS="$(dirname "$(readlink -f "$0")")"
# --path may name a checkout of another repo than this script's (the prefix+X
# binding is server-wide, so whichever repo's tmux-dev.sh ran last may have
# bound its copy): act on that checkout's repo, not on the one we live in.
for ((i = 1; i < $#; i++)); do
  if [ "${!i}" = --path ]; then
    j=$((i + 1)); ROOT="$(git -C "${!j}" rev-parse --show-toplevel 2>/dev/null || true)"
  fi
done
. "$SCRIPTS/wt-lib.sh"
MAIN="$(main_checkout)"

# Never run the copy that lives inside a worktree: bash reads a script as it
# executes, and removing the worktree would delete the file mid-run. The main
# checkout's copy is the one that survives everything this script does. (On a
# branch where the script is new, main has no copy yet; then keep this one.)
self="$(readlink -f "$0")"
main_self="$(readlink -f "$MAIN/scripts/wt-done.sh" 2>/dev/null || true)"
if [ -n "$main_self" ] && [ -x "$main_self" ] && [ "$self" != "$main_self" ]; then exec "$main_self" "$@"; fi

branch=""; from_path=""; force=0; from_tmux=0
while [ $# -gt 0 ]; do
  case "$1" in
    --path) shift; from_path="${1:-}"; [ -n "$from_path" ] || die "--path needs a value";;
    --force) force=1;;
    --from-tmux) from_tmux=1;;   # internal: re-entry from the tmux server, see below
    -*) die "unknown option: $1";;
    *) [ -z "$branch" ] || die "unexpected argument: $1"; branch="$1";;
  esac
  shift
done
if [ -n "$from_path" ]; then
  [ -z "$branch" ] || die "give a branch or --path, not both"
  branch="$(git -C "$from_path" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  [ -n "$branch" ] || die "not inside a git checkout: $from_path"
fi
[ -n "$branch" ] || die "usage: wt-done.sh <branch>|--path <dir> [--force]"
case " $PROTECTED_BRANCHES " in *" $branch "*) die "$branch never has a worktree";; esac

path="$(worktree_path_for "$branch")"
[ -n "$path" ] || die "no worktree has '$branch' checked out (wt list)"
SESSION="$(session_name "$branch")"

drop_sandbox_stubs "$path"
if [ "$force" = 0 ] && [ -n "$(git -C "$path" status --porcelain)" ]; then
  die "$path has uncommitted or untracked changes. Commit them (the branch keeps them), or --force to lose them"
fi
# Unpushed commits survive on the local branch ref; just say where they are.
if upstream="$(git -C "$path" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null)"; then
  n="$(git -C "$path" rev-list --count '@{upstream}..HEAD')"
  if [ "$n" != 0 ]; then echo "note: $n commit(s) not on $upstream, they stay on the local branch $branch"; fi
else
  echo "note: $branch was never pushed, the work stays on the local branch only"
fi

# Run from a pane of the very session being closed, the kill (teardown fires it
# before git removes the worktree) would take this script down with it and the
# worktree would stay. Hand the job to the tmux server instead: it outlives the
# session, detach-on-destroy off (tmux-dev.sh) moves this client to another
# session, and tmux shows the result in a view when the job finishes.
if [ "$from_tmux" = 0 ] && [ -n "${TMUX:-}" ] && [ "$(tmux display-message -p '#S')" = "$SESSION" ]; then
  fflag=""; if [ "$force" = 1 ]; then fflag=" --force"; fi
  echo "closing $SESSION from the tmux server (this pane goes away with it)"
  exec tmux run-shell -b "'$self' '$branch'$fflag --from-tmux"
fi

cd "$MAIN"
if [ "$force" = 1 ]; then wt remove -f "$branch"; else wt remove "$branch"; fi
tmux kill-session -t "=$SESSION" 2>/dev/null || true   # teardown normally did it already
echo "closed: session $SESSION and worktree $path. Branch $branch kept, wtgo $branch rebuilds it"
