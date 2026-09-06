#!/usr/bin/env bash
# One command from branch name to a running, attached dev session — whether the
# branch is brand new, exists without a worktree, or already has one:
#   scripts/wt-new.sh <branch> [base=origin/dev] [--prompt <file-or-text>] [--no-attach]
# (or: make go BRANCH=feat/x)
# wt create / wt checkout → .wt.toml hooks (deps, env, ports, detached tmux
# session) → attach. Detach with prefix+d; you land back where you started.
# --prompt writes a PROMPT.md at the worktree root and the session's claude pane
#   starts on it, on fable in plan mode, so you get a plan back to review (see
#   tmux-dev.sh). A readable file is copied, anything else is taken as the
#   literal prompt text. On a session that is already up the claude pane is
#   restarted on the brief; its previous conversation stays resumable.
# --no-attach leaves the session detached, so several wtgo calls can run back
#   to back from one shell.
# Tab completion for branch names: source scripts/wt-go.bash (see the guide).
set -euo pipefail
SCRIPTS="$(dirname "$(readlink -f "$0")")"
. "$SCRIPTS/wt-lib.sh"
branch=""; base=""; prompt=""; prompt_file=""; no_attach=0
while [ $# -gt 0 ]; do
  case "$1" in
    # Resolve a brief file right here: the script cds to the main checkout
    # below, so a relative path given from a worktree would be read from the
    # wrong place (and, worse, taken as literal prompt text). Anything that
    # looks like a path but is not a file is an error rather than a brief.
    --prompt)
      shift; prompt="${1:-}"; [ -n "$prompt" ] || die "--prompt needs a value"
      if [ -f "$prompt" ]; then prompt_file="$(readlink -f "$prompt")"; prompt=""
      else case "$prompt" in */*|*.md|*.txt) die "--prompt: no such file: $prompt";; esac
      fi;;
    --no-attach) no_attach=1;;
    -*) die "unknown option: $1";;
    *) if [ -z "$branch" ]; then branch="$1"
       elif [ -z "$base" ]; then base="$1"
       else die "unexpected argument: $1"; fi;;
  esac
  shift
done
base="${base:-origin/dev}"
[ -n "$branch" ] || die "usage: wt-new.sh <branch> [base] [--prompt <file-or-text>] [--no-attach]"

# `wtgo all` — after a reboot: bring every set-up worktree's session back,
# detached, then hand over the session picker. Only worktrees carrying a
# .env.worktree count: one without (an agent scratch checkout) would fall back
# to the main checkout's ports and collide with it.
if [ "$branch" = all ]; then
  [ -z "$prompt$prompt_file" ] || die "--prompt takes a single branch, not 'all'"
  ROOT="$(main_checkout)"
  started=0
  while IFS= read -r p; do
    { [ "$p" != "$ROOT" ] && [ -f "$p/.env.worktree" ]; } || continue
    echo "==> $p"
    ROOT="$p" "$SCRIPTS/tmux-dev.sh" --no-attach || echo "warning: session for $p failed"
    started=$((started + 1))
  done < <(git -C "$ROOT" worktree list --porcelain | sed -n 's#^worktree ##p')
  [ "$started" -gt 0 ] || die "no set-up worktrees found (none has a .env.worktree)"
  echo "$started session(s) up — pick one (prefix+s later works too):"
  if [ -n "${TMUX:-}" ]; then exec tmux choose-tree -wZ -O name
  else exec tmux attach-session \; choose-tree -wZ -O name; fi
fi
# A worktree holding the default branch becomes wt's "main" and breaks path
# resolution (see the guide's gotchas); stage/main are just as off-limits.
case " $PROTECTED_BRANCHES " in *" $branch "*) die "$branch never gets a worktree — work on a feature branch";; esac
# Work against the main checkout wherever this runs from — a worktree cwd, or a
# shell whose environment carries a stale ROOT from an old tmux session.
ROOT="$(main_checkout)"
cd "$ROOT"
if [ -z "$(worktree_path_for "$branch")" ]; then
  if git show-ref --verify --quiet "refs/heads/$branch" ||
     git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    # The branch already exists: adopt it into a worktree (wt create would
    # refuse), the same hooks run.
    wt checkout "$branch"
  else
    # A local ref can silently be stale (a branch cut from it then lacks recent
    # fixes); refresh the remote ones so the origin/dev default is current.
    case "$base" in origin/*) git fetch --quiet origin "${base#origin/}" || echo "warning: fetch failed, using cached $base";; esac
    wt create "$branch" "$base"
  fi
fi
path="$(worktree_path_for "$branch")"
[ -n "$path" ] || die "wt create did not produce a worktree for $branch"
# Drop the brief for the claude pane. On a brand new worktree the session is
# already up by now (the wt post_create hook starts it), so --brief tells
# tmux-dev.sh to restart the claude pane on it instead of leaving the file
# unread (what used to happen).
flags=""
if [ -n "$prompt_file" ]; then cp "$prompt_file" "$path/PROMPT.md"; flags="$flags --brief"
elif [ -n "$prompt" ]; then printf '%s\n' "$prompt" > "$path/PROMPT.md"; flags="$flags --brief"
fi
if [ "$no_attach" = 1 ]; then flags="$flags --no-attach"; fi
# session exists → attach (or switch-client inside tmux)
ROOT="$path" exec "$SCRIPTS/tmux-dev.sh" $flags
