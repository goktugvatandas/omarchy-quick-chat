#!/bin/bash
set -euo pipefail

if [[ "${QUICK_CHAT_DISPOSABLE:-}" != "1" ]]; then
  echo "Refusing to alter the active desktop; run only in a disposable Omarchy guest." >&2
  exit 2
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PLUGIN_ID="goktugvatandas.quick-chat"
QUICK_CHAT_REPO="${QUICK_CHAT_REPO:-file://$ROOT}"
ARTIFACT_DIR="${QUICK_CHAT_ARTIFACT_DIR:-$ROOT/test/acceptance/artifacts}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
CONFIG_FILE="$CONFIG_HOME/omarchy/quick-chat/config.json"
TEST_TEMP="$(mktemp -d)"
BACKUP_FILE="$TEST_TEMP/config.json"
HAD_CONFIG=0
OTHER_ADDRESS=""

fail() {
  printf 'Quick Chat acceptance failed: %s\n' "$*" >&2
  exit 1
}

for command in omarchy omarchy-shell hyprctl jq wtype wl-copy wl-paste rg; do
  command -v "$command" >/dev/null || fail "missing required command: $command"
done

mkdir -p "$ARTIFACT_DIR"
if [[ -f "$CONFIG_FILE" ]]; then
  cp -- "$CONFIG_FILE" "$BACKUP_FILE"
  HAD_CONFIG=1
fi

cleanup() {
  omarchy-shell shell hide "$PLUGIN_ID" >/dev/null 2>&1 || true
  if [[ "$HAD_CONFIG" == "1" ]]; then
    mkdir -p "$(dirname -- "$CONFIG_FILE")"
    cp -- "$BACKUP_FILE" "$CONFIG_FILE"
  else
    rm -f -- "$CONFIG_FILE"
  fi
  rm -rf -- "$TEST_TEMP"
}
trap cleanup EXIT

record_clients() {
  local name="$1"
  hyprctl clients -j >"$ARTIFACT_DIR/$name-clients.json"
}

quick_chat_count() {
  hyprctl clients -j | jq '[.[] | select(.title == "Quick Chat")] | length'
}

wait_for_quick_chat() {
  local attempt
  for attempt in $(seq 1 50); do
    if [[ "$(quick_chat_count)" == "1" ]]; then
      return 0
    fi
    sleep 0.1
  done
  fail "exactly one Quick Chat window did not appear"
}

wait_for_hidden() {
  local attempt
  for attempt in $(seq 1 30); do
    if [[ "$(quick_chat_count)" == "0" ]]; then
      return 0
    fi
    sleep 0.1
  done
  fail "Quick Chat window remained mapped"
}

record_state() {
  local name="$1"
  local clients_file="$ARTIFACT_DIR/$name-clients.json"
  local state_file="$ARTIFACT_DIR/$name-state.json"
  local count
  hyprctl clients -j >"$clients_file"
  count="$(jq '[.[] | select(.title == "Quick Chat")] | length' "$clients_file")"
  [[ "$count" == "1" ]] || fail "$name resolved $count Quick Chat windows"
  jq -e '[.[] | select(.title == "Quick Chat")][0]
    | {
        address,
        title,
        class,
        at,
        size,
        floating,
        fullscreen,
        tags: (.tags // [])
      }' "$clients_file" >"$state_file"
  printf '%s\n' "$state_file"
}

state_address() {
  jq -r '.address' "$1"
}

assert_same_window_state() {
  local before="$1"
  local after="$2"
  local label="$3"
  local before_signature
  local after_signature
  before_signature="$(jq -c '{address,at,size,floating,fullscreen}' "$before")"
  after_signature="$(jq -c '{address,at,size,floating,fullscreen}' "$after")"
  [[ "$before_signature" == "$after_signature" ]] \
    || fail "$label changed window geometry or compositor state"
}

focus_quick_chat() {
  local address="$1"
  hyprctl dispatch focuswindow "address:$address" >/dev/null
  sleep 0.15
}

key() {
  wtype -k "$1"
}

modified_key() {
  local modifier="$1"
  local key_name="$2"
  wtype -M "$modifier" -k "$key_name" -m "$modifier"
}

double_modified_key() {
  local first="$1"
  local second="$2"
  local key_name="$3"
  wtype -M "$first" -M "$second" -k "$key_name" -m "$second" -m "$first"
}

capture_artifact() {
  local name="$1"
  local captured
  captured="$(omarchy capture screenshot fullscreen save | tail -n 1)"
  [[ -s "$captured" ]] || fail "capture produced no image for $name"
  cp -- "$captured" "$ARTIFACT_DIR/$name.png"
}

capture_fixture() {
  local name="$1"
  local fixture="$2"
  record_clients "$name-before-summon"
  omarchy-shell shell summon "$PLUGIN_ID" \
    "{\"acceptanceFixture\":\"$fixture\"}"
  wait_for_quick_chat
  sleep 1
  record_state "$name-after-summon" >/dev/null
  capture_artifact "$name"
  record_state "$name-before-hide" >/dev/null
  omarchy-shell shell hide "$PLUGIN_ID"
  wait_for_hidden
  record_clients "$name-after-hide"
}

omarchy plugin add "$QUICK_CHAT_REPO" --enable --yes
omarchy-shell shell listPlugins \
  | jq -e --arg id "$PLUGIN_ID" '.[] | select(.id == $id and .enabled == true)'

if rg -n '\bopacity\s*:' --glob '*.qml' "$ROOT"; then
  fail "plugin QML must not override compositor opacity"
fi

hyprctl binds -j >"$ARTIFACT_DIR/hyprland-binds.json"
jq -e 'any(.[]; (.description // "") == "Toggle window floating/tiling")' \
  "$ARTIFACT_DIR/hyprland-binds.json" >/dev/null \
  || fail "Super+T floating/tiling binding is unavailable"
jq -e 'any(.[]; (.description // "") == "Full width")' \
  "$ARTIFACT_DIR/hyprland-binds.json" >/dev/null \
  || fail "Super+Alt+F maximize binding is unavailable"
jq -e 'any(.[]; (.description // "") == "Move window")' \
  "$ARTIFACT_DIR/hyprland-binds.json" >/dev/null \
  || fail "Super+drag move binding is unavailable"
rg -q 'window\.startSystemMove\(\)' "$ROOT/QuickChat.qml" \
  || fail "header drag is not wired to the standard window move API"

OTHER_ADDRESS="$(hyprctl activewindow -j | jq -r '.address // empty')"
[[ -n "$OTHER_ADDRESS" ]] || fail "acceptance requires another toplevel for focus transfer"

record_clients 00-before-initial-summon
omarchy-shell shell summon "$PLUGIN_ID" '{"profileId":"codex"}'
wait_for_quick_chat
sleep 0.35
INITIAL_STATE="$(record_state 01-after-initial-summon)"
QUICK_ADDRESS="$(state_address "$INITIAL_STATE")"

jq -e '
  .title == "Quick Chat"
  and .floating == true
  and (.size[0] >= 596 and .size[0] <= 644)
  and (.size[1] >= 596 and .size[1] <= 644)
  and ((.tags | index("default-opacity")) != null)
' "$INITIAL_STATE" >/dev/null \
  || fail "initial window is not a themed, approximately 620x620 floating toplevel"

# Autofocus is verified without a click by round-tripping composer text through
# its normal select/copy behavior.
wtype "FOCUS_SENTINEL"
modified_key ctrl a
modified_key ctrl c
sleep 0.1
[[ "$(wl-paste --no-newline)" == "FOCUS_SENTINEL" ]] \
  || fail "composer did not accept typing immediately after summon"
key BackSpace
capture_artifact compact-chat

FOCUS_BEFORE="$(record_state 02-before-focus-transfer)"
hyprctl dispatch focuswindow "address:$OTHER_ADDRESS" >/dev/null
sleep 0.55
FOCUS_AWAY="$(record_state 03-after-focus-transfer)"
[[ "$(hyprctl activewindow -j | jq -r '.address')" == "$OTHER_ADDRESS" ]] \
  || fail "another window could not keep focus while Quick Chat remained open"
assert_same_window_state "$FOCUS_BEFORE" "$FOCUS_AWAY" "focus transfer"
focus_quick_chat "$QUICK_ADDRESS"
record_state 04-after-focus-return >/dev/null

TILE_BEFORE="$(record_state 05-before-super-t)"
modified_key logo t
sleep 0.65
TILED_STATE="$(record_state 06-after-super-t)"
jq -e '.floating == false' "$TILED_STATE" >/dev/null \
  || fail "Super+T did not leave Quick Chat tiled"
[[ "$(state_address "$TILE_BEFORE")" == "$(state_address "$TILED_STATE")" ]] \
  || fail "Super+T replaced the Quick Chat toplevel"
modified_key logo t
sleep 0.35
RESTORED_FLOAT="$(record_state 07-after-super-t-restore)"
jq -e '.floating == true' "$RESTORED_FLOAT" >/dev/null \
  || fail "Super+T did not restore floating state"

HISTORY_BEFORE="$(record_state 08-before-history-shortcut)"
modified_key ctrl h
sleep 0.2
HISTORY_STATE="$(record_state 09-after-history-shortcut)"
assert_same_window_state "$HISTORY_BEFORE" "$HISTORY_STATE" "History shortcut"
capture_artifact history
key Home
key End
key Down
key Up
key space
modified_key ctrl h
sleep 0.15
record_state 10-after-history-return >/dev/null

SETTINGS_BEFORE="$(record_state 11-before-settings-shortcut)"
modified_key ctrl comma
sleep 0.2
SETTINGS_STATE="$(record_state 12-after-settings-shortcut)"
assert_same_window_state "$SETTINGS_BEFORE" "$SETTINGS_STATE" "Settings shortcut"
capture_artifact settings
key Tab
modified_key shift Tab
modified_key alt Left
sleep 0.15
record_state 13-after-alt-left >/dev/null

# From the focused composer, Shift+Tab reaches the header's maximize button.
modified_key ctrl l
modified_key shift Tab
HEADER_MAX_BEFORE="$(record_state 14-before-header-maximize)"
key Return
sleep 0.45
HEADER_MAX="$(record_state 15-after-header-maximize)"
jq -e '.fullscreen == 1' "$HEADER_MAX" >/dev/null \
  || fail "header maximize did not enter compositor maximized state"
key Return
sleep 0.4
HEADER_RESTORE="$(record_state 16-after-header-restore)"
jq -e '.fullscreen == 0' "$HEADER_RESTORE" >/dev/null \
  || fail "header maximize did not restore the standard window"

focus_quick_chat "$QUICK_ADDRESS"
SUPER_MAX_BEFORE="$(record_state 17-before-super-alt-f)"
double_modified_key logo alt f
sleep 0.45
SUPER_MAX="$(record_state 18-after-super-alt-f)"
jq -e '.fullscreen == 1' "$SUPER_MAX" >/dev/null \
  || fail "Super+Alt+F did not enter compositor maximized state"
double_modified_key logo alt f
sleep 0.4
SUPER_RESTORE="$(record_state 19-after-super-alt-f-restore)"
jq -e '.fullscreen == 0' "$SUPER_RESTORE" >/dev/null \
  || fail "Super+Alt+F did not restore the standard window"

# The static contract above verifies header startSystemMove and the compositor
# bind verifies Super+drag. This exact-address move proves the resulting
# FloatingWindow is a normal compositor-movable toplevel.
MOVE_BEFORE="$(record_state 20-before-window-move)"
MOVE_X="$(jq '.at[0] + 37' "$MOVE_BEFORE")"
MOVE_Y="$(jq '.at[1] + 29' "$MOVE_BEFORE")"
hyprctl dispatch movewindowpixel \
  "exact $MOVE_X $MOVE_Y,address:$QUICK_ADDRESS" >/dev/null
sleep 0.25
MOVE_AFTER="$(record_state 21-after-window-move)"
[[ "$(jq -c '.at' "$MOVE_BEFORE")" != "$(jq -c '.at' "$MOVE_AFTER")" ]] \
  || fail "standard window did not move"

capture_artifact private-off
double_modified_key ctrl shift p
sleep 0.15
capture_artifact private-on
if cmp -s "$ARTIFACT_DIR/private-off.png" "$ARTIFACT_DIR/private-on.png"; then
  fail "private shortcut did not change the visible icon state"
fi
double_modified_key ctrl shift p

modified_key ctrl k
sleep 0.2
capture_artifact model-picker
key Home
key End
key Up
key Down
key Right
sleep 0.2
key Left
key space
key Escape
[[ "$(quick_chat_count)" == "1" ]] \
  || fail "Escape from the model picker closed the window"

modified_key ctrl period
sleep 0.2
capture_artifact effort-picker
key Home
key End
key Up
key Down
key space
[[ "$(quick_chat_count)" == "1" ]] \
  || fail "effort keyboard selection closed the window"

modified_key ctrl l
wtype "line one"
modified_key ctrl Return
wtype "line two"
modified_key ctrl a
modified_key ctrl c
sleep 0.1
[[ "$(wl-paste --no-newline)" == $'line one\nline two' ]] \
  || fail "Ctrl+Enter did not insert a composer newline"
key Return
sleep 0.2
modified_key ctrl l
wtype "POST_SEND"
modified_key ctrl a
modified_key ctrl c
[[ "$(wl-paste --no-newline)" == "POST_SEND" ]] \
  || fail "Enter did not send and clear the composer"
key BackSpace

omarchy-shell shell summon "$PLUGIN_ID" '{"acceptanceFixture":"streamed"}'
wait_for_quick_chat
sleep 0.25
capture_artifact before-new-chat
modified_key ctrl n
sleep 0.2
capture_artifact after-new-chat
if cmp -s "$ARTIFACT_DIR/before-new-chat.png" "$ARTIFACT_DIR/after-new-chat.png"; then
  fail "Ctrl+N did not visibly create a fresh conversation"
fi

modified_key ctrl h
sleep 0.15
ESCAPE_PAGE_BEFORE="$(record_state 22-before-page-escape)"
key Escape
sleep 0.15
ESCAPE_PAGE_AFTER="$(record_state 23-after-page-escape)"
assert_same_window_state "$ESCAPE_PAGE_BEFORE" "$ESCAPE_PAGE_AFTER" "page Escape"
key Escape
wait_for_hidden
record_clients 24-after-window-escape

capture_fixture attachment-preview attachment
capture_fixture streamed-answer streamed
capture_fixture approval-card approval
capture_fixture error-state error

for artifact in \
  compact-chat model-picker effort-picker history settings attachment-preview \
  streamed-answer approval-card error-state; do
  [[ -s "$ARTIFACT_DIR/$artifact.png" ]] \
    || fail "missing acceptance artifact: $artifact.png"
done

hyprctl reload >/dev/null
sleep 0.5
CONFIG_ERRORS="$(hyprctl configerrors)"
[[ -z "$CONFIG_ERRORS" ]] || fail "Hyprland reported config errors after reload"

printf 'Acceptance artifacts: %s\n' "$ARTIFACT_DIR"
