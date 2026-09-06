# `wtgo <branch>` — go to a branch's dev session, creating whatever is missing
# (worktree, tmux session, even the branch). Same engine as `make go`; the
# function exists so bash can tab-complete branch names, which make cannot do
# for variable values. `wtdone <branch>` is the reverse: session + worktree
# gone, branch kept (scripts/wt-done.sh).
#
# Install once:  echo 'source ~/code/resslab-hub/scripts/wt-go.bash' >> ~/.bashrc
#
# Completion is two-tier: while your input matches an existing worktree, only
# worktrees are offered — a bare `wtgo <TAB>` is exactly "what was I working
# on". Only when nothing matches does it widen to every local and origin
# branch, minus dev/stage/main (never checked out in a worktree).
_WTGO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

wtgo() { "$_WTGO_ROOT/scripts/wt-new.sh" "$@"; }
wtdone() { "$_WTGO_ROOT/scripts/wt-done.sh" "$@"; }

_wt_worktrees() {
  git -C "$_WTGO_ROOT" worktree list --porcelain 2>/dev/null |
    sed -n 's#^branch refs/heads/##p' | grep -Ev '^(dev|stage|main)$'
}

_wtgo() {
  local cur=${COMP_WORDS[COMP_CWORD]}
  local wts
  wts=$(_wt_worktrees)
  COMPREPLY=( $(compgen -W "all $wts" -- "$cur") )
  if [ ${#COMPREPLY[@]} -eq 0 ]; then
    local branches
    branches=$( { echo "$wts"
                  git -C "$_WTGO_ROOT" for-each-ref --format='%(refname:short)' refs/heads refs/remotes/origin |
                    sed 's#^origin/##'; } 2>/dev/null |
                grep -Ev '^(HEAD|origin|dev|stage|main)$' | sort -u )
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
