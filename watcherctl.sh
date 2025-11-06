#!/usr/bin/env zsh
set -euo pipefail
setopt nobgnice

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.jamesdurkee.sn2md-watch"
PLIST_SOURCE="$SCRIPT_DIR/$LABEL.plist"
PLIST_TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_PREFIX="[watcherctl]"

usage() {
  cat <<'USAGE'
Usage: watcherctl.sh --start | --stop | --restart
USAGE
}

require_plist() {
  if [[ ! -f "$PLIST_SOURCE" ]]; then
    print -u2 "$LOG_PREFIX plist missing at $PLIST_SOURCE"
    exit 1
  fi
}

install_plist() {
  mkdir -p "$(dirname "$PLIST_TARGET")"
  if [[ ! -f "$PLIST_TARGET" || "$PLIST_SOURCE" -nt "$PLIST_TARGET" ]]; then
    cp "$PLIST_SOURCE" "$PLIST_TARGET"
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

ACTION=""
case "${1-}" in
  --start) ACTION="start" ;;
  --stop) ACTION="stop" ;;
  --restart) ACTION="restart" ;;
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
esac
