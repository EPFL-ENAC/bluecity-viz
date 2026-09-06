#!/usr/bin/env bash
# Install the Claude Code desktop-notification hooks (user-level, all projects).
# Run it yourself — Claude's sandbox cannot edit ~/.claude/settings.json:
#   ! scripts/claude-notify-install.sh
#
# What it does (idempotent, re-run after editing scripts/claude-notify.sh):
#   1. Copies scripts/claude-notify.sh -> ~/.local/bin/claude-notify so the
#      hooks work in every repo, independent of this branch's checkout.
#   2. Merges into ~/.claude/settings.json (backup kept alongside):
#        Notification/permission_prompt -> claude-notify permission
#        Notification/idle_prompt       -> claude-notify idle
#        Stop                           -> claude-notify stop, replacing the
#        old generic "notify-send 'Claude Code' 'Task completed!'" entry
#        (other Stop hooks are left untouched).
#   3. Rebinds prefix+s from `choose-tree -sZ` to `choose-tree -wZ` in
#      ~/.tmux.conf: with one dev window per session, -s hid the four panes
#      behind a second expand; -w shows each session's window immediately.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin/claude-notify"
SETTINGS="$HOME/.claude/settings.json"

command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

# 1. install the handler
mkdir -p "$HOME/.local/bin"
install -m 755 "$HERE/claude-notify.sh" "$BIN"
echo "installed $BIN"

# 2. merge the hooks into user settings
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
backup="$SETTINGS.bak-$(date +%Y%m%d-%H%M%S)"
cp "$SETTINGS" "$backup"
jq --arg bin "$BIN" '
  .hooks //= {} |
  .hooks.Notification = (
    ((.hooks.Notification // [])
     | map(select(((.hooks // []) | any(.command // "" | contains("claude-notify"))) | not)))
    + [{matcher: "permission_prompt",
        hooks: [{type: "command", command: ($bin + " permission")}]},
       {matcher: "idle_prompt",
        hooks: [{type: "command", command: ($bin + " idle")}]}]
  ) |
  .hooks.Stop = (
    ((.hooks.Stop // [])
     | map(select(((.hooks // []) | any(.command // ""
         | (contains("claude-notify stop") or startswith("notify-send")))) | not)))
    + [{matcher: "*", hooks: [{type: "command", command: ($bin + " stop")}]}]
  )
' "$backup" > "$SETTINGS"
echo "updated $SETTINGS (backup: $backup); hook changes:"
diff <(jq .hooks "$backup") <(jq .hooks "$SETTINGS") || true

# 3. prefix+s: sessions expanded to their dev window, panes one expand away
if [ -f "$HOME/.tmux.conf" ] && grep -q 'bind s choose-tree -sZ -O name' "$HOME/.tmux.conf"; then
  sed -i 's/bind s choose-tree -sZ -O name/bind s choose-tree -wZ -O name/' "$HOME/.tmux.conf"
  echo "rebound prefix+s to choose-tree -wZ in ~/.tmux.conf"
elif ! grep -qs 'bind s choose-tree' "$HOME/.tmux.conf"; then
  printf 'bind s choose-tree -wZ -O name\n' >> "$HOME/.tmux.conf"
  echo "added prefix+s choose-tree binding to ~/.tmux.conf"
fi
tmux source-file "$HOME/.tmux.conf" 2>/dev/null || true

echo "done — running Claude sessions pick the hooks up on their next start"
