# `wtgo <branch>` — go to a branch's dev session, creating whatever is missing
# (worktree, tmux session, even the branch). Same engine as `make go`; the
# function exists so bash can tab-complete branch names, which make cannot do
# for variable values. `wtdone <branch>` is the reverse: session + worktree
# gone, branch kept (scripts/wt-done.sh).
#
# Install once:  echo 'source ~/code/bluecity-viz/scripts/wt-go.bash' >> ~/.bashrc
# Source this file ONCE, from any repo that has the tooling: the functions find
# the repo you are standing in, so one source line serves every ported repo.
# Standing somewhere else (your home directory, a repo without the tooling), the
# commands use WTGO_DEFAULT_REPO if you set it, else the repo this file lives
# in, and say so on stderr. To keep another repo as that default:
#   WTGO_DEFAULT_REPO=~/code/resslab-hub
#   source ~/code/bluecity-viz/scripts/wt-go.bash
#
# Completion is two-tier: while your input matches an existing worktree, only
# worktrees are offered — a bare `wtgo <TAB>` is exactly "what was I working
# on". Only when nothing matches does it widen to every local and origin
# branch, minus the protected ones (never checked out in a worktree).
_WTGO_ROOT="${WTGO_DEFAULT_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# The repo you are standing in, if it has the worktree tooling; else the default
# repo. From inside a worktree, git's common dir points back at the main
# checkout, which is where the scripts are run from anyway.
# Prints the path either way; returns 1 when it had to fall back, so the callers
# can say which repo they picked instead of acting on the wrong one silently.
_wt_root() {
  local common root
  if common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); then
    root=$(dirname "$common")
    if [ -x "$root/scripts/wt-new.sh" ]; then printf '%s' "$root"; return 0; fi
  fi
  printf '%s' "$_WTGO_ROOT"; return 1
}
# Resolve for a command that is about to act: a fallback is worth one line on
# stderr, because "which repo does this create a worktree in" is not obvious.
_wt_root_loud() {
  local root
  root=$(_wt_root) ||
    echo "wtgo: not inside a repo with the worktree tooling, using $root" >&2
  printf '%s' "$root"
}

wtgo() { "$(_wt_root_loud)/scripts/wt-new.sh" "$@"; }
wtdone() { "$(_wt_root_loud)/scripts/wt-done.sh" "$@"; }

# The union of every repo's protected branches (PROTECTED_BRANCHES in each
# wt-lib.sh): a name filtered here is only hidden from completion, and none of
# these is ever worked on in a worktree, whichever repo you stand in.
_WT_NEVER='^(dev|stage|main)$'

_wt_worktrees() {
  git -C "$(_wt_root)" worktree list --porcelain 2>/dev/null |
    sed -n 's#^branch refs/heads/##p' | grep -Ev "$_WT_NEVER"
}

_wtgo() {
  local cur=${COMP_WORDS[COMP_CWORD]}
  local wts root
  root=$(_wt_root)
  wts=$(_wt_worktrees)
  COMPREPLY=( $(compgen -W "all $wts" -- "$cur") )
  if [ ${#COMPREPLY[@]} -eq 0 ]; then
    local branches
    branches=$( { echo "$wts"
                  git -C "$root" for-each-ref --format='%(refname:short)' refs/heads refs/remotes/origin |
                    sed 's#^origin/##'; } 2>/dev/null |
                grep -Ev '^(HEAD|origin)$' | grep -Ev "$_WT_NEVER" | sort -u )
    COMPREPLY=( $(compgen -W "$branches" -- "$cur") )
  fi
}
complete -F _wtgo wtgo

# wtdone closes environments that exist, so it completes worktrees only.
_wtdone() {
  local cur=${COMP_WORDS[COMP_CWORD]}
  COMPREPLY=( $(compgen -W "$(_wt_worktrees)" -- "$cur") )
}
complete -F _wtdone wtdone
