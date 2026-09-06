#!/usr/bin/env bash
# Claude Code hook -> desktop notification, clickable to jump to the session.
#
# Usage (registered in ~/.claude/settings.json by scripts/claude-notify-install.sh):
#   claude-notify permission   # Notification hook, matcher permission_prompt
#   claude-notify idle         # Notification hook, matcher idle_prompt
#   claude-notify stop         # Stop hook
#
# Reads the hook's JSON payload on stdin, derives the tmux session the agent
# lives in (resslab-hub/<branch> naming, see session_name() in wt-lib.sh — but
# self-contained so the installed copy in ~/.local/bin works for any repo),
# and raises a notification titled with the session name. Clicking it jumps to
# that session: if a terminal already has a tmux client attached, that client
# switches to the session (your open terminal becomes the right place — GNOME
# Wayland offers no way to raise a window from a script, but flipping what an
# attached client shows needs no window management at all); only when no client
# exists does it open a new terminal attached to the session. Either way the
# claude pane is selected, so the prompt that asked for you is in front.
#
# The hook process must return immediately, so the interactive notify-send
# (which blocks until the notification is clicked or dismissed) runs in a
# detached worker via setsid. A newer notification for the same session
# replaces the older one instead of stacking.
set -u

KIND="${1:-permission}"

# ---------- worker: blocks on notify-send, handles the click -----------------
if [ "$KIND" = --worker ]; then
  TITLE=$2 BODY=$3 ICON=$4 SESSION=$5 CWD=$6 IDFILE=$7

  open_terminal() {
    # Debounce: a replaced notification leaves an earlier worker waiting on the
    # same notification id, so one click can wake several workers.
    local now last
    now=$(date +%s); last=$(cat "$IDFILE.opened" 2>/dev/null || echo 0)
    [ $((now - last)) -lt 3 ] && return 0
    echo "$now" > "$IDFILE.opened"

    # Resolve the session at click time, not notification time: the server may
    # have restarted or the session been recreated since the notification rose.
    local sess="$SESSION"
    if [ -z "$sess" ] || ! tmux has-session -t "=$sess" 2>/dev/null; then
      sess=$(tmux list-panes -a -F '#{session_name} #{pane_current_path}' 2>/dev/null |
        awk -v p="$CWD" '$2 == p {print $1; exit}')
    fi

    if [ -n "$sess" ] && tmux has-session -t "=$sess" 2>/dev/null; then
      # Put the claude pane in front so the waiting prompt is what you see.
      local pane
      pane=$(tmux list-panes -s -t "=$sess" -F '#{pane_id} #{pane_title}' 2>/dev/null |
        awk '$2 == "claude" {print $1; exit}')
      [ -n "$pane" ] && tmux select-pane -t "$pane" 2>/dev/null
      # A terminal with a tmux client attached is the place the user already
      # looks at: flip the most recently used client to this session instead of
      # spawning another window. Only with no client anywhere do we open one.
      local client
      client=$(tmux list-clients -F '#{client_activity} #{client_name}' 2>/dev/null |
        sort -rn | awk 'NR==1 {print $2}')
      if [ -n "$client" ]; then
        tmux switch-client -c "$client" -t "=$sess" 2>/dev/null && return 0
      fi
      if command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal --window -- tmux attach-session -t "=$sess"
      elif command -v x-terminal-emulator >/dev/null 2>&1; then
        x-terminal-emulator -e tmux attach-session -t "=$sess"
      fi
    else
      if command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal --window --working-directory="$CWD"
      elif command -v x-terminal-emulator >/dev/null 2>&1; then
        x-terminal-emulator
      fi
    fi
  }

  prev_id=$(cat "$IDFILE" 2>/dev/null || true)
  out=$(mktemp "${TMPDIR:-/tmp}/claude-notify.XXXXXX")
  # -p prints the notification id; -A makes notify-send wait and print the
  # action name when clicked. Stream to a file so the id is usable for
  # replacement while we are still waiting for the click.
  notify-send -a 'Claude Code' -i "$ICON" -p -A default='Open session' \
    ${prev_id:+-r "$prev_id"} -- "$TITLE" "$BODY" > "$out" 2>/dev/null &
  ns_pid=$!
  for _ in $(seq 30); do
    id=$(head -n1 "$out" 2>/dev/null)
    case "$id" in (*[0-9]*) echo "$id" > "$IDFILE"; break;; esac
    sleep 0.1
  done
  wait "$ns_pid" 2>/dev/null
  [ "$(tail -n1 "$out" 2>/dev/null)" = default ] && open_terminal
  rm -f "$out"
  exit 0
fi

# ---------- hook entry: parse payload, derive session, detach worker ---------
command -v notify-send >/dev/null 2>&1 || exit 0
payload=$(cat 2>/dev/null || true)

json_get() {
  if command -v jq >/dev/null 2>&1; then
    jq -r --arg k "$1" '.[$k] // empty' <<<"$payload" 2>/dev/null
  else
    python3 -c 'import json,sys; d=json.load(sys.stdin); v=d.get(sys.argv[1],""); print(v if v is not None else "")' \
      "$1" <<<"$payload" 2>/dev/null
  fi
}

cwd=$(json_get cwd); [ -n "$cwd" ] || cwd=$PWD
message=$(json_get message)

# Branch and repo of the checkout the agent runs in. WT_BRANCH is exported into
# the claude pane by tmux-dev.sh and survives into hook processes.
branch="${WT_BRANCH:-$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null || true)}"
repo=$(basename -s .git "$(git -C "$cwd" config --get remote.origin.url 2>/dev/null)" 2>/dev/null)
[ -n "$repo" ] || repo=$(basename "$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || echo "$cwd")")

# tmux session: <repo>/<branch> with the characters tmux forbids mapped, same
# transform as session_name() in wt-lib.sh; fall back to scanning panes for one
# whose current path is this checkout (covers repos with other naming schemes).
session=""
if [ -n "$branch" ] && [ "$branch" != HEAD ]; then
  candidate="$repo/$(printf '%s' "$branch" | tr '.:' '--')"
  tmux has-session -t "=$candidate" 2>/dev/null && session=$candidate
fi
if [ -z "$session" ]; then
  session=$(tmux list-panes -a -F '#{session_name} #{pane_current_path}' 2>/dev/null |
    awk -v p="$cwd" '$2 == p {print $1; exit}')
fi

display="${session:-$repo${branch:+:$branch}}"
case "$KIND" in
  permission) title="🔐 $display"; icon=dialog-question
              body="${message:-Claude needs your permission}";;
  idle)       title="💬 $display"; icon=dialog-information
              body="${message:-Claude is waiting for your input}";;
  stop)       title="✅ $display"; icon=dialog-information
              body="${message:-Task finished — ready for review}";;
  *)          title="Claude Code — $display"; icon=dialog-information
              body="${message:-$KIND}";;
esac

idfile="${XDG_RUNTIME_DIR:-/tmp}/claude-notify.$(printf '%s' "$display" | tr -c 'A-Za-z0-9' '_').id"
setsid -f "$0" --worker "$title" "$body" "$icon" "$session" "$cwd" "$idfile" \
  </dev/null >/dev/null 2>&1
exit 0
