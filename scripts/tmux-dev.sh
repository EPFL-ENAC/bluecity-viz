#!/usr/bin/env bash
# One tmux session per checkout, named "<repo>/<branch>", one window with four
# titled panes: claude (left half), backend (uvicorn), frontend (vite), shell
# stacked on the right. Ports come from .env.worktree
# (written by wt-setup.sh); the main checkout keeps 8000/5173.
#   scripts/tmux-dev.sh              create the session for this checkout, or attach if it exists
#   scripts/tmux-dev.sh --no-attach  create it detached (what the wt hook does)
#   scripts/tmux-dev.sh --brief      also fire the checkout's PROMPT.md brief in the claude pane,
#                                    even when the session is already running (what wtgo --prompt does)
set -euo pipefail
SCRIPTS="$(dirname "$(readlink -f "$0")")"
. "$SCRIPTS/wt-lib.sh"
# ROOT arrives exported from wt-new.sh / wt-setup.sh; wt-lib has read it, so drop
# the export before any tmux command. If this command is the one that starts the
# tmux server, an exported ROOT becomes part of the server's environment, every
# shell in every pane inherits it, and any wt script run from those shells then
# targets this checkout no matter what directory it is run from. The
# set-environment call scrubs a server that an earlier version already poisoned.
# The .env.worktree keys get the same treatment: a server started from a shell
# that had a worktree's file sourced would give its ports to every later session,
# including the main checkout's, whose frontend still looks for the backend on 8000.
export -n ROOT || true
tmux set-environment -gu ROOT 2>/dev/null || true
for key in $ENV_WORKTREE_KEYS; do tmux set-environment -gu "$key" 2>/dev/null || true; done
load_env_worktree
BRANCH="$(current_branch)"
SESSION="$(session_name "$BRANCH")"
MAIN="$(main_checkout)"
# Server-wide tweaks, refreshed on every run (a no-op call when the server is
# not up yet; called again right after new-session for the run that starts it).
# - detach-on-destroy off: when a session dies (x in the choose-tree, wtdone,
#   the teardown hook), the clients watching it hop to the most recently used
#   remaining session instead of detaching; with none left tmux still exits.
# - prefix+X: a small menu on the current session — plain kill, or wt-done.sh
#   (kill + remove the worktree + branch kept), with a
#   confirmed force variant when the worktree has uncommitted changes. The
#   binding is server-wide and the last tmux-dev.sh to run owns it, whatever
#   repo it came from (bluecity-viz carries the same tooling), so it bakes no
#   script path in: wt-done.sh is resolved at key time from the pane's own
#   checkout, through the main checkout of that repo (the copy that survives
#   the worktree removal), and gets the branch from the pane's path (--path).
#   run-shell runs from the server, so the removal survives the session kill
#   and its output pops up in a view when it finishes.
server_options() {
  tmux set-option -g detach-on-destroy off
#   The snippet is parsed by tmux before sh sees it, so it uses backticks and
#   single quotes only: no $ (tmux expands $NAME in double-quoted strings) and
#   no double quotes (the confirm-before variant nests it inside some).
#   <git-common-dir>/.. is the main checkout.
  local resolve="cd '#{pane_current_path}' && \`git rev-parse --path-format=absolute --git-common-dir\`/../scripts/wt-done.sh --path '#{pane_current_path}' --from-tmux"
  local close="run-shell -b \"$resolve\""
  local discard="confirm-before -p 'discard uncommitted changes and remove the worktree? (y/n)' \"run-shell -b \\\"$resolve --force\\\"\""
  tmux bind-key X display-menu -T " #S " \
    "kill session (stay in tmux)"              k kill-session \
    "" \
    "done: also remove worktree, keep branch"  d "$close" \
    "force done: DISCARD uncommitted changes"  D "$discard"
}
server_options 2>/dev/null || true

ATTACH=1; BRIEF=0
for arg in "$@"; do
  case "$arg" in
    --no-attach) ATTACH=0;;
    --brief) BRIEF=1;;
    *) die "unknown option: $arg";;
  esac
done

attach() {
  [ "$ATTACH" = 1 ] || return 0
  if [ -n "${TMUX:-}" ]; then tmux switch-client -t "=$SESSION"; else tmux attach-session -t "=$SESSION"; fi
}
print_urls() {
  cat <<URLS
session : $SESSION   (prefix+s to switch)
frontend: http://localhost:$FRONTEND_PORT/
backend : http://127.0.0.1:$BACKEND_PORT/docs
URLS
}

# Every pane exports .env.worktree so the Makefiles (BACKEND_PORT) and vite
# (FRONTEND_PORT, and BACKEND_PORT for its /api proxy) see the same values.
# No file (the main checkout): unset the keys instead, so nothing inherited from a
# worktree shell or the tmux server sticks to this pane.
LOAD='set -a; if [ -f "$(git rev-parse --show-toplevel)/.env.worktree" ]; then . "$(git rev-parse --show-toplevel)/.env.worktree"; else unset '"$ENV_WORKTREE_KEYS"'; fi; set +a'

# What the claude pane runs. A PROMPT.md at the checkout root is a one-shot
# brief (wtgo --prompt, or written by hand): rename it, then start claude on it
# with the model and permission mode below. Plan mode on purpose, so the agent
# comes back with a plan to review instead of editing straight away. Renaming
# before the run means a session recreated later (wtgo all after a reboot)
# resumes that conversation instead of firing the brief a second time.
# With no brief, resume the checkout's last conversation; a fresh worktree has
# none, --continue exits nonzero, and a new conversation starts instead.
BRIEF_MODEL="${WT_BRIEF_MODEL-fable}"          # empty = whatever claude defaults to
BRIEF_MODE="${WT_BRIEF_PERMISSION_MODE-plan}"  # empty = whatever claude defaults to
claude_cmd() {
  local flags=""
  if [ -f "$ROOT/PROMPT.md" ]; then
    [ -z "$BRIEF_MODEL" ] || flags="$flags --model $BRIEF_MODEL"
    [ -z "$BRIEF_MODE" ] || flags="$flags --permission-mode $BRIEF_MODE"
    echo "mv PROMPT.md PROMPT.sent.md && claude$flags \"\$(cat PROMPT.sent.md)\""
  else
    echo "claude --continue || claude"
  fi
}
# A brief cannot reach a claude that is already running, so restart the pane on
# it. Nothing is lost: the conversation it replaces stays resumable with
# `claude --continue`. The pane is found by the @wt_role option set at creation,
# not by its title, because claude rewrites the pane title as it works.
send_brief() {
  local pane
  pane="$(tmux list-panes -t "=$SESSION" -F '#{pane_id} #{@wt_role}' | awk '$2 == "claude" { print $1; exit }')"
  if [ -z "$pane" ]; then
    echo "wt: no claude pane in $SESSION (session from an older tmux-dev.sh?). PROMPT.md kept, kill the session and run wtgo again"
    return 0
  fi
  local cmd; cmd="$(claude_cmd)"
  tmux respawn-pane -k -t "$pane" -c "$ROOT"
  tmux send-keys -t "$pane" "$LOAD; $cmd" C-m
  tmux select-pane -t "$pane"
  echo "brief sent to the claude pane of $SESSION"
}

if tmux has-session -t "=$SESSION" 2>/dev/null; then
  # The wt post_create hook already started this session, before wtgo could
  # write PROMPT.md, so this is where a new worktree's brief fires.
  if [ "$BRIEF" = 1 ] && [ -f "$ROOT/PROMPT.md" ]; then send_brief; fi
  print_urls; attach; exit 0
fi

# Mirror the server panes' output to plain files: the claude pane's agent runs
# sandboxed with no access to the tmux socket, so log files inside the checkout
# are the only way it can see why a server misbehaves. Fresh per session.
LOGS="$ROOT/.wt-logs"; mkdir -p "$LOGS"
pipe_log() { : > "$LOGS/$1.log"; tmux pipe-pane -t "$2" -o "exec cat >> '$LOGS/$1.log'"; }

# One window, four titled panes: claude fills the left half; the right half
# stacks backend / frontend / shell. prefix+arrows move between panes, prefix+z
# zooms one to full screen, and the prefix+s / prefix+w previews show the whole
# layout at a glance. claude has focus when you attach.
tmux new-session -d -s "$SESSION" -n dev -c "$ROOT"
server_options   # this run may have just started the server
P_CLAUDE="$(tmux display-message -p -t "=$SESSION:dev" '#{pane_id}')"
P_BACKEND="$(tmux split-window -h -l 50% -P -F '#{pane_id}' -t "$P_CLAUDE" -c "$ROOT/backend")"
P_FRONTEND="$(tmux split-window -v -l 67% -P -F '#{pane_id}' -t "$P_BACKEND" -c "$ROOT/frontend")"
P_SHELL="$(tmux split-window -v -l 50% -P -F '#{pane_id}' -t "$P_FRONTEND" -c "$ROOT")"
# Titles are for the eye; @wt_role is the stable handle scripts look panes up
# by (send_brief here, claude-notify.sh): claude rewrites its pane title as it
# works, and a title is not a tmux target anyway.
for spec in "$P_CLAUDE claude" "$P_BACKEND backend" "$P_FRONTEND frontend" "$P_SHELL shell"; do
  set -- $spec
  tmux select-pane -t "$1" -T "$2"
  tmux set-option -p -t "$1" @wt_role "$2"
done
tmux set-option -w -t "=$SESSION:dev" pane-border-status top

tmux send-keys -t "$P_BACKEND" "$LOAD; make dev" C-m
pipe_log backend "$P_BACKEND"
tmux send-keys -t "$P_FRONTEND" "$LOAD; pnpm run dev" C-m   # no Makefile in frontend/
pipe_log frontend "$P_FRONTEND"
tmux send-keys -t "$P_CLAUDE" "$LOAD; $(claude_cmd)" C-m
tmux send-keys -t "$P_SHELL" "$LOAD; clear" C-m
tmux select-pane -t "$P_CLAUDE"

print_urls
attach
