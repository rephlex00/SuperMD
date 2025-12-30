#!/usr/bin/env zsh
set -euo pipefail
setopt nobgnice

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_PATH="${1:-$SCRIPT_DIR/jobs.yaml}"
LOG_PREFIX="[sn2md-watch]"

require_cmd() {
  local name="$1"
  local hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    print -u2 "$LOG_PREFIX missing dependency: $name. $hint"
    exit 127
  fi
}

require_cmd yq "Install with: brew install yq"
require_cmd fswatch "Install with: brew install fswatch"
require_cmd python3 "Install with: brew install python"

if [[ ! -f "$CONFIG_PATH" ]]; then
  print -u2 "$LOG_PREFIX config file not found: $CONFIG_PATH"
  exit 1
fi

expand_path() {
  python3 - <<'PYCODE' "$1"
import os, sys
print(os.path.expanduser(sys.argv[1]))
PYCODE
}

collect_inputs() {
  local cfg="$1"
  yq -r '
    . as $root
    | $root.jobs[]
    | (.input // $root.defaults.input)
  ' "$cfg" 2>/dev/null || return 1
}

typeset -aU WATCH_PATHS=()
while IFS= read -r raw_path; do
  [[ -z "$raw_path" ]] && continue
  expanded="$(expand_path "$raw_path")"
  [[ -z "$expanded" ]] && continue
  if [[ ! -d "$expanded" ]]; then
    print -u2 "$LOG_PREFIX warning: $expanded does not exist; skipping"
    continue
  fi
  WATCH_PATHS+="$expanded"
done < <(collect_inputs "$CONFIG_PATH")

(( ${#WATCH_PATHS[@]} > 0 )) || {
  print -u2 "$LOG_PREFIX no valid input directories resolved from $CONFIG_PATH"
  exit 1
}

print "$LOG_PREFIX watching ${#WATCH_PATHS[@]} directories from $CONFIG_PATH"

while IFS= read -r event_path; do
  [[ -z "$event_path" ]] && continue
  print "$LOG_PREFIX $(date '+%F %T') change detected at $event_path"
  "$SCRIPT_DIR/sn2md-batches.sh" --config "$CONFIG_PATH"
done < <(fswatch --recursive --latency=2 --one-per-batch "${WATCH_PATHS[@]}")
