#!/usr/bin/env zsh
set -euo pipefail

# ==========================================
# sn2md-batches — YAML-driven multi-job runner for sn2md
#
# Default config: jobs.yaml      (override with: --config file.yaml)
# Parallelism:     --jobs N      (default = 1; override to run in parallel)
# Colors:          auto on TTY   (disable with: --no-color)
# Extra args:      passed through for configless jobs (e.g., --no-progress)
# Requires:        yq (Mike Farah) — brew install yq
# ==========================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_CONF="$SCRIPT_DIR/jobs.yaml"
CONF_FILE="$DEFAULT_CONF"
USER_ARGS=()
JOBS_LIMIT=""   # set later after parsing
COLOR=true

# ---------- helpers ----------
trim() { sed -E 's/^[[:space:]]+|[[:space:]]+$//g' <<<"$1"; }
tilde_expand() { [[ "$1" == "~"* ]] && echo "${1/#\~/$HOME}" || echo "$1"; }
is_tty() { [[ -t 1 ]]; }
# ---------- parse args ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      shift
      [[ $# -gt 0 ]] || { print -u2 "--config requires a filename"; exit 64; }
      CONF_FILE="$1"
      ;;
    --config=*) CONF_FILE="${1#*=}" ;;
    --jobs)
      shift
      [[ $# -gt 0 ]] || { print -u2 "--jobs requires a number"; exit 64; }
      JOBS_LIMIT="$1"
      ;;
    --jobs=*) JOBS_LIMIT="${1#*=}" ;;
    --no-color) COLOR=false ;;
    *) USER_ARGS+=("$1") ;;
  esac
  shift
done

command -v yq >/dev/null 2>&1 || { print -u2 "yq not installed. Try: brew install yq"; exit 127; }
[[ -r "$CONF_FILE" ]] || { print -u2 "Config not readable: $CONF_FILE"; exit 66; }

# ---------- colors ----------
if $COLOR && is_tty && command -v tput >/dev/null 2>&1; then
  C_RESET="$(tput sgr0)"
  C_DIM="$(tput dim)"
  C_BOLD="$(tput bold)"
  C_GREEN="$(tput setaf 2)"
  C_YELLOW="$(tput setaf 3)"
  C_RED="$(tput setaf 1)"
  C_BLUE="$(tput setaf 4)"
  C_CYAN="$(tput setaf 6)"
else
  C_RESET=""; C_DIM=""; C_BOLD=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""; C_CYAN="";
fi

# ---------- defaults from YAML ----------
DEF_INPUT="$(yq -r '.defaults.input // ""' "$CONF_FILE")"
DEF_OUTPUT="$(yq -r '.defaults.output // ""' "$CONF_FILE")"
DEF_ENV_FILE="$(yq -r '.defaults.env_file // ""' "$CONF_FILE")"
DEF_FORCE="$(yq -r '.defaults.flags.force // false' "$CONF_FILE")"
DEF_PROGRESS="$(yq -r '.defaults.flags.progress // true' "$CONF_FILE")"
DEF_LEVEL="$(yq -r '.defaults.flags.level // "INFO"' "$CONF_FILE")"
DEF_MODEL="$(yq -r '.defaults.flags.model // "gpt-4o-mini"' "$CONF_FILE")"

DEF_EXTRA_ARGS=()
while IFS= read -r arg; do
  [[ -n "$arg" ]] && DEF_EXTRA_ARGS+=("$arg")
done < <(yq -r '.defaults.extra_args[]? // empty' "$CONF_FILE")

# ---------- load jobs as JSON lines ----------
mapfile -t JOBS < <(yq -c '.jobs[]' "$CONF_FILE")
TOTAL="${#JOBS[@]}"
(( TOTAL > 0 )) || { print -u2 "No jobs found in $CONF_FILE"; exit 64; }

# ---------- decide concurrency ----------
if [[ -z "$JOBS_LIMIT" ]]; then
  JOBS_LIMIT=1
fi
[[ "$JOBS_LIMIT" =~ ^[0-9]+$ ]] || { print -u2 "--jobs must be an integer"; exit 64; }
(( JOBS_LIMIT >= 1 )) || { print -u2 "--jobs must be >= 1"; exit 64; }

print "${C_BOLD}${C_BLUE}sn2md-batches:${C_RESET} jobs=$TOTAL  parallel=$JOBS_LIMIT  config=$CONF_FILE"

# ---------- run a single job in background (buffered output) ----------
# We buffer each job's log in a temp file to avoid interleaved lines.
run_job() {
  local idx="$1" job_json="$2" logf ret
  logf="$(mktemp -t sn2md_job_${idx}.XXXXXX)"

  {
    local name in_path out_path cfg_path env_file_job force progress level model
    name="$(yq -r '.name // ""' <<<"$job_json")"
    in_path="$(yq -r '.input' <<<"$job_json")"
    out_path="$(yq -r '.output // ""' <<<"$job_json")"
    cfg_path="$(yq -r '.config' <<<"$job_json")"
    env_file_job="$(yq -r '.env_file // ""' <<<"$job_json")"

    force="$(yq -r '.flags.force // ""' <<<"$job_json")"
    progress="$(yq -r '.flags.progress // ""' <<<"$job_json")"
    level="$(yq -r '.flags.level // ""' <<<"$job_json")"
    model="$(yq -r '.flags.model // ""' <<<"$job_json")"

    # per-job extra args merged with defaults
    local -a job_extra_args
    job_extra_args=("${DEF_EXTRA_ARGS[@]}")
    while IFS= read -r arg; do
      [[ -n "$arg" ]] && job_extra_args+=("$arg")
    done < <(yq -r '.extra_args[]? // empty' <<<"$job_json")

    # defaults
    [[ -z "$in_path" || "$in_path" == "null" ]] && in_path="$DEF_INPUT"
    [[ -z "$out_path" || "$out_path" == "null" ]] && out_path="$DEF_OUTPUT"
    [[ -z "$env_file_job" || "$env_file_job" == "null" ]] && env_file_job="$DEF_ENV_FILE"
    [[ -z "$force" || "$force" == "null" ]] && force="$DEF_FORCE"
    [[ -z "$progress" || "$progress" == "null" ]] && progress="$DEF_PROGRESS"
    [[ -z "$level" || "$level" == "null" ]] && level="$DEF_LEVEL"
    [[ -z "$model" || "$model" == "null" ]] && model="$DEF_MODEL"

    # expand & trim
    in_path="$(tilde_expand "$(trim "$in_path")")"
    out_path="$(tilde_expand "$(trim "$out_path")")"
    cfg_path="$(tilde_expand "$(trim "$cfg_path")")"
    env_file_job="$(tilde_expand "$(trim "$env_file_job")")"

    # validate
    if [[ -z "$in_path" ]]; then
      echo "Input missing after defaults (job='${name:-unnamed}')" >&2
      echo "__RESULT__:FAIL" >>"$logf"
      return
    fi
    if [[ ! -e "$in_path" ]]; then
      echo "Input path not found: $in_path (job='${name:-unnamed}')" >&2
      echo "__RESULT__:FAIL" >>"$logf"
      return
    fi
    if [[ -n "$cfg_path" && "$cfg_path" != "null" && ! -r "$cfg_path" ]]; then
      echo "Config not readable: $cfg_path (job='${name:-unnamed}')" >&2
      echo "__RESULT__:FAIL" >>"$logf"
      return
    fi
    [[ -n "$out_path" ]] || { echo "Output missing after defaults (job='${name:-unnamed}')" >&2; echo "__RESULT__:FAIL" >>"$logf"; return; }
    mkdir -p "$out_path"

    echo "sn2md job: ${name:-unnamed}"
    echo "  input : $in_path"
    echo "  output: $out_path"
    if [[ -n "$cfg_path" && "$cfg_path" != "null" ]]; then
      echo "  config: $cfg_path"
    else
      echo "  config: (none)"
    fi
    if [[ -n "$cfg_path" && "$cfg_path" != "null" ]]; then
      echo "  model : (from config)"
      echo "  level : (from config)"
      echo "  force : (from config)"
      echo "  progress: (from config)"
    else
      echo "  model : $model"
      echo "  level : $level"
      echo "  force : $force"
      echo "  progress: $progress"
    fi

    local -a SN_ARGS
    SN_ARGS=(-o "$out_path")
    if [[ -n "$cfg_path" && "$cfg_path" != "null" ]]; then
      SN_ARGS+=(-c "$cfg_path")
    else
      SN_ARGS+=(-m "$model" -l "$level")
      [[ "$force" == "true" ]] && SN_ARGS+=("--force")
      if [[ "$progress" == "true" ]]; then
        SN_ARGS+=("--progress")
      else
        SN_ARGS+=("--no-progress")
      fi
      SN_ARGS+=("${job_extra_args[@]}" "${USER_ARGS[@]}")
    fi

    # scoped env
    if [[ -n "$env_file_job" && -r "$env_file_job" ]]; then
      set -o allexport
      source "$env_file_job"
      set +o allexport
    fi

    if sn2md "${SN_ARGS[@]}" directory "$in_path"; then
      echo "__RESULT__:OK" >>"$logf"
    else
      echo "__RESULT__:FAIL" >>"$logf"
    fi
  } >"$logf" 2>&1

  ret=0
  grep -q "__RESULT__:OK" "$logf" || ret=1

  # pretty print buffered block with color + prefix
  local title="${C_BOLD}${C_CYAN}[job $idx]${C_RESET} ${C_BOLD}"
  if (( ret == 0 )); then
    echo "${title}${C_GREEN}SUCCESS${C_RESET}"
  else
    echo "${title}${C_RED}FAILED${C_RESET}"
  fi
  # strip the __RESULT__ marker line(s) before printing
  sed '/^__RESULT__:/d' "$logf" | sed "s/^/  /"

  rm -f "$logf"
  return $ret
}

# ---------- run in parallel (bounded) ----------
typeset -a PIDS
typeset -A PID_STATUS  # pid -> 0/1
ok=0 err=0

concurrency="$JOBS_LIMIT"
index=0

for job in "${JOBS[@]}"; do
  (( index++ ))

  # launch background
  ( run_job "$index" "$job" ) &
  pid=$!
  PIDS+=("$pid")

  # throttle
  while (( ${#PIDS[@]} >= concurrency )); do
    wait "${PIDS[1]}" && PID_STATUS["${PIDS[1]}"]=0 || PID_STATUS["${PIDS[1]}"]=1
    PIDS=("${PIDS[@]:1}")
  done
done

# wait remaining
for pid in "${PIDS[@]}"; do
  wait "$pid" && PID_STATUS["$pid"]=0 || PID_STATUS["$pid"]=1
done

# tally
for p in "${(@k)PID_STATUS}"; do
  if (( PID_STATUS[$p] == 0 )); then (( ok++ )); else (( err++ )); fi
done

# footer
if (( err == 0 )); then
  echo "${C_BOLD}${C_GREEN}All done.${C_RESET} total=$TOTAL ok=$ok err=$err"
  exit 0
else
  echo "${C_BOLD}${C_YELLOW}Completed with errors.${C_RESET} total=$TOTAL ok=$ok err=$err"
  exit 1
fi
