#!/usr/bin/env zsh
set -euo pipefail
setopt nobgnice

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.sn2md.watch"
PLIST_TEMPLATE="$SCRIPT_DIR/$LABEL.plist.in"
PLIST_TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_PREFIX="[watcherctl]"

usage() {
  cat <<'USAGE'
Usage: watcherctl.sh --start | --stop | --restart | --status | --uninstall
USAGE
}

require_plist() {
  if [[ ! -f "$PLIST_TEMPLATE" ]]; then
    print -u2 "$LOG_PREFIX plist template missing at $PLIST_TEMPLATE"
    exit 1
  fi
}

install_plist() {
  mkdir -p "$(dirname "$PLIST_TARGET")"
  local tmp
  tmp="$(mktemp "${TMPDIR:-/tmp}/watcherctl.XXXXXX")"
  local project_dir="$SCRIPT_DIR"
  local home_dir="$HOME"
  # Capture current PATH to ensure user-installed tools (uv, yq, etc.) are found
  local current_path="$PATH"
  python3 - "$PLIST_TEMPLATE" "$tmp" "$project_dir" "$home_dir" "$current_path" <<'PYCODE'
import sys

template, target, project_dir, home_dir, env_path = sys.argv[1:]
with open(template, "r", encoding="utf-8") as src:
    content = src.read()
content = (
    content
    .replace("{{PROJECT_DIR}}", project_dir)
    .replace("{{HOME}}", home_dir)
    .replace("{{PATH}}", env_path)
)
with open(target, "w", encoding="utf-8") as dst:
    dst.write(content)
PYCODE
  if [[ ! -f "$PLIST_TARGET" ]] || ! cmp -s "$tmp" "$PLIST_TARGET"; then
    mv "$tmp" "$PLIST_TARGET"
  else
    rm -f "$tmp"
  fi
}

start_service() {
  require_plist
  install_plist
  if launchctl bootstrap "gui/$UID" "$PLIST_TARGET" 2>/dev/null; then
    print "$LOG_PREFIX loaded $LABEL"
  else
    if launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1; then
      print "$LOG_PREFIX already loaded; refreshing"
    else
      print -u2 "$LOG_PREFIX failed to bootstrap $LABEL"
      exit 1
    fi
  fi
  launchctl kickstart -k "gui/$UID/$LABEL" >/dev/null 2>&1 || true
}

stop_service() {
  if launchctl bootout "gui/$UID/$LABEL" >/dev/null 2>&1; then
    print "$LOG_PREFIX unloaded $LABEL"
  else
    print "$LOG_PREFIX already stopped or not loaded"
  fi
}

status_service() {
  local job="gui/$UID/$LABEL"
  if launchctl print "$job" >/dev/null 2>&1; then
    print "$LOG_PREFIX $LABEL is loaded (see launchctl print $job for details)"
  else
    if [[ -f "$PLIST_TARGET" ]]; then
      print "$LOG_PREFIX $LABEL is not loaded but plist exists at $PLIST_TARGET"
    else
      print "$LOG_PREFIX $LABEL is not loaded and plist missing at $PLIST_TARGET"
    fi
  fi
}

uninstall_service() {
  stop_service
  if [[ -f "$PLIST_TARGET" ]]; then
    rm -f "$PLIST_TARGET"
    print "$LOG_PREFIX removed $PLIST_TARGET"
  else
    print "$LOG_PREFIX no plist to remove at $PLIST_TARGET"
  fi
}

ACTION=""
case "${1-}" in
  --start) ACTION="start" ;;
  --stop) ACTION="stop" ;;
  --restart) ACTION="restart" ;;
  --status) ACTION="status" ;;
  --uninstall) ACTION="uninstall" ;;
  *)
    usage
    exit 64
    ;;
esac

shift || true
if (( $# > 0 )); then
  print -u2 "$LOG_PREFIX unexpected arguments: $*"
  usage
  exit 64
fi

case "$ACTION" in
  start) start_service ;;
  stop) stop_service ;;
  restart)
    stop_service
    start_service
    ;;
  status) status_service ;;
  uninstall) uninstall_service ;;
esac
