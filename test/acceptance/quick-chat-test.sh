#!/bin/bash
set -euo pipefail

if [[ "${QUICK_CHAT_DISPOSABLE:-}" != "1" ]]; then
  echo "Refusing to alter the active desktop; run only in a disposable Omarchy guest." >&2
  exit 2
fi

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PLUGIN_ID="community.quick-chat"
QUICK_CHAT_REPO="${QUICK_CHAT_REPO:-file://$ROOT}"
ARTIFACT_DIR="${QUICK_CHAT_ARTIFACT_DIR:-$ROOT/test/acceptance/artifacts}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
CONFIG_FILE="$CONFIG_HOME/omarchy/quick-chat/config.json"
BACKUP_FILE="$(mktemp)"
HAD_CONFIG=0

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
  rm -f -- "$BACKUP_FILE"
}
trap cleanup EXIT

capture_fixture() {
  local name="$1"
  local payload="$2"
  local captured
  omarchy-shell shell summon "$PLUGIN_ID" "$payload"
  sleep 1
  captured="$(omarchy capture screenshot fullscreen save | tail -n 1)"
  cp -- "$captured" "$ARTIFACT_DIR/$name.png"
  omarchy-shell shell hide "$PLUGIN_ID"
}

omarchy plugin add "$QUICK_CHAT_REPO" --enable --yes
omarchy-shell shell listPlugins \
  | jq -e --arg id "$PLUGIN_ID" '.[] | select(.id == $id and .enabled == true)'

omarchy-shell shell summon "$PLUGIN_ID" '{"profileId":"codex"}'
wtype "Explain this window"
wtype -M ctrl -k Return -m ctrl
omarchy-shell shell hide "$PLUGIN_ID"

capture_fixture compact '{}'
capture_fixture model-picker '{"acceptanceFixture":"picker"}'
capture_fixture attachment-preview '{"acceptanceFixture":"attachment"}'
capture_fixture streamed-answer '{"acceptanceFixture":"streamed"}'
capture_fixture approval-card '{"acceptanceFixture":"approval"}'
capture_fixture expanded-settings '{"acceptanceFixture":"settings"}'
capture_fixture error-state '{"acceptanceFixture":"error"}'

for artifact in \
  compact model-picker attachment-preview streamed-answer approval-card expanded-settings error-state; do
  test -s "$ARTIFACT_DIR/$artifact.png"
done

printf 'Acceptance artifacts: %s\n' "$ARTIFACT_DIR"
