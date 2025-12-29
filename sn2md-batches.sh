#!/usr/bin/env zsh
set -euo pipefail
setopt nobgnice

# ==========================================================
# sn2md-batches — YAML-driven multi-job runner for sn2md
# ----------------------------------------------------------
#  * Default config : jobs.yaml (override with --config)
#  * Parallelism    : --jobs N  (default = 1)
#  * Dry run        : --dry-run (no filesystem changes)
#  * Colors         : auto on TTY (disable with --no-color)
#  * Setup          : --setup (bootstrap .venv with sn2md and exit)
#  * Extra args     : forwarded to sn2md for configless jobs
#  * Dependencies   : yq + sn2md (setup handled via uv when requested)
# ==========================================================

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly DEFAULT_CONF="$SCRIPT_DIR/jobs.yaml"
readonly DEFAULT_VENV="$SCRIPT_DIR/.venv"
UV_PYTHON_VERSION="${UV_PYTHON_VERSION:-3.11}"
readonly UV_PYTHON_VERSION

CONF_FILE="$DEFAULT_CONF"
JOBS_LIMIT=1
COLOR=true
DRY_RUN=false
SETUP=false
SN2MD_CMD="${SN2MD_EXEC:-}"
HAS_NON_SETUP_ARGS=false

typeset -a USER_ARGS=()
typeset -a DEF_EXTRA_ARGS=()
typeset -a JOBS=()

typeset TOTAL_JOBS=0

typeset C_RESET="" C_DIM="" C_BOLD="" C_GREEN="" C_YELLOW="" C_RED="" C_BLUE="" C_CYAN=""

# usage: show CLI options and exit when requested
usage() {
  cat <<'USAGE'
Usage: sn2md-batches.sh [options] [-- passthrough sn2md args]

  --config FILE     YAML config file (default: jobs.yaml)
  --jobs N          Concurrency (default: 1)
  --dry-run         Preview commands without running sn2md
  --no-color        Disable ANSI colors
  --setup           Bootstrap the local sn2md environment (.venv) and exit
  --help            Show this help

All additional arguments are forwarded to sn2md when a job has no TOML config.
USAGE
}

# log_error: print an error message in red to stderr
log_error() {
  local msg="$1"
  print -u2 "${C_RED}error:${C_RESET} $msg"
}

# log_warn: emit non-fatal warnings in yellow
log_warn() {
  local msg="$1"
  print -u2 "${C_YELLOW}warning:${C_RESET} $msg"
}

# log_info: emit dimmed informational messages
log_info() {
  local msg="$1"
  print "${C_DIM}$msg${C_RESET}"
}

# die: print an error and terminate with an optional status code
die() {
  local msg="$1"
  local code="${2:-1}"
  log_error "$msg"
  exit "$code"
}

# trim: remove leading/trailing whitespace
trim() { sed -E 's/^[[:space:]]+|[[:space:]]+$//g' <<<"$1"; }
# tilde_expand: convert leading ~ into $HOME
tilde_expand() { [[ "$1" == "~"* ]] && echo "${1/#\~/$HOME}" || echo "$1"; }

# init_colors: compute ANSI color codes when TTY supports them
init_colors() {
  if $COLOR && [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
    C_RESET="$(tput sgr0)"
    C_DIM="$(tput dim)"
    C_BOLD="$(tput bold)"
    C_GREEN="$(tput setaf 2)"
    C_YELLOW="$(tput setaf 3)"
    C_RED="$(tput setaf 1)"
    C_BLUE="$(tput setaf 4)"
    C_CYAN="$(tput setaf 6)"
  fi
}

# parse_args: handle CLI flags, enforcing --setup exclusivity
parse_args() {
  HAS_NON_SETUP_ARGS=false
  USER_ARGS=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --config)
        shift
        [[ $# -gt 0 ]] || die "--config requires a filename" 64
        CONF_FILE="$1"
        HAS_NON_SETUP_ARGS=true
        ;;
      --config=*)
        CONF_FILE="${1#*=}"
        HAS_NON_SETUP_ARGS=true
        ;;
      --jobs)
        shift
        [[ $# -gt 0 ]] || die "--jobs requires a number" 64
        JOBS_LIMIT="$1"
        HAS_NON_SETUP_ARGS=true
        ;;
      --jobs=*)
        JOBS_LIMIT="${1#*=}"
        HAS_NON_SETUP_ARGS=true
        ;;
      --no-color)
        COLOR=false
        HAS_NON_SETUP_ARGS=true
        ;;
      --dry-run)
        DRY_RUN=true
        HAS_NON_SETUP_ARGS=true
        ;;
      --setup)
        SETUP=true
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      --)
        shift
        (( $# > 0 )) && HAS_NON_SETUP_ARGS=true
        USER_ARGS+=("$@")
        break
        ;;
      *)
        USER_ARGS+=("$1")
        HAS_NON_SETUP_ARGS=true
        ;;
    esac
    shift || true
  done

  [[ "$JOBS_LIMIT" =~ ^[0-9]+$ ]] || die "--jobs must be an integer" 64
  (( JOBS_LIMIT >= 1 )) || die "--jobs must be >= 1" 64

  if $SETUP && ( $HAS_NON_SETUP_ARGS || (( ${#USER_ARGS[@]} > 0 )) ); then
    die "--setup must be used by itself (no additional flags or arguments)" 64
  fi
}

# require_command: ensure a dependency is available or abort
require_command() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    if [[ -n "$hint" ]]; then
      die "$cmd not found. $hint" 127
    fi
    die "$cmd not found" 127
  fi
}

# discover_sn2md: locate the sn2md executable from env, .venv, or PATH
discover_sn2md() {
  local resolved
  if [[ -n "$SN2MD_CMD" ]]; then
    if [[ -x "$SN2MD_CMD" ]]; then
      return
    elif resolved="$(command -v "$SN2MD_CMD" 2>/dev/null || true)" && [[ -n "$resolved" ]]; then
      SN2MD_CMD="$resolved"
      return
    else
      die "SN2MD_EXEC points to a non-existent command: $SN2MD_CMD" 127
    fi
  fi

  if [[ -x "$DEFAULT_VENV/bin/sn2md" ]]; then
    SN2MD_CMD="$DEFAULT_VENV/bin/sn2md"
    return
  fi

  if command -v sn2md >/dev/null 2>&1; then
    SN2MD_CMD="$(command -v sn2md)"
    return
  fi

  SN2MD_CMD=""
}

# bootstrap_sn2md: create the uv-managed venv and install sn2md + llm-ollama
bootstrap_sn2md() {
  local uv_bin="${UV_BIN:-}"
  local venv_path="$DEFAULT_VENV"

  [[ -n "$uv_bin" ]] || uv_bin="$(command -v uv 2>/dev/null || true)"
  [[ -n "$uv_bin" ]] || die "uv not found. Install it from https://astral.sh/uv or set UV_BIN=/path/to/uv."

  log_info "Bootstrapping sn2md with uv (python ${UV_PYTHON_VERSION})…"

  if [[ ! -d "$venv_path" ]]; then
    "$uv_bin" venv --python "$UV_PYTHON_VERSION" "$venv_path" || die "uv venv failed"
  fi

  if [[ ! -x "$venv_path/bin/sn2md" ]]; then
    "$uv_bin" pip install --python "$venv_path/bin/python" sn2md || die "uv pip install sn2md failed"
  fi

  if ! "$uv_bin" pip install --python "$venv_path/bin/python" llm-ollama >/dev/null 2>&1; then
    log_warn "llm-ollama plugin installation failed; retry with UV_BIN pointing at uv if installed elsewhere"
  fi

  SN2MD_CMD="$venv_path/bin/sn2md"
}

DEF_INPUT=""
DEF_OUTPUT=""
DEF_ENV_FILE=""
DEF_FORCE=""
DEF_PROGRESS=""
DEF_LEVEL=""
DEF_MODEL=""

# load_defaults: read shared defaults from the YAML config
load_defaults() {
  if [[ ! -r "$CONF_FILE" && "$CONF_FILE" == "$DEFAULT_CONF" ]]; then
     die "Config file '$CONF_FILE' not found.
    To start, copy the example config:
      cp jobs.example.yaml jobs.yaml
    Then edit jobs.yaml to set your input/output paths." 66
  fi
  [[ -r "$CONF_FILE" ]] || die "Config not readable: $CONF_FILE" 66
  DEF_INPUT="$(yq eval -r '.defaults.input // ""' "$CONF_FILE")"
  DEF_OUTPUT="$(yq eval -r '.defaults.output // ""' "$CONF_FILE")"
  DEF_ENV_FILE="$(yq eval -r '.defaults.env_file // ""' "$CONF_FILE")"
  DEF_FORCE="$(yq eval -r '.defaults.flags.force // false' "$CONF_FILE")"
  DEF_PROGRESS="$(yq eval -r '.defaults.flags.progress // true' "$CONF_FILE")"
  DEF_LEVEL="$(yq eval -r '.defaults.flags.level // "INFO"' "$CONF_FILE")"
  DEF_MODEL="$(yq eval -r '.defaults.flags.model // "gpt-4o-mini"' "$CONF_FILE")"

  DEF_EXTRA_ARGS=()
  while IFS= read -r arg; do
    [[ -n "$arg" ]] && DEF_EXTRA_ARGS+=("$arg")
  done < <(yq eval -r '.defaults.extra_args // [] | .[]' "$CONF_FILE")
}

# load_jobs: collect all job definitions into the JOBS array
load_jobs() {
  local total
  total="$(yq eval '.jobs | length' "$CONF_FILE")"
  total="${total:-0}"
  (( total > 0 )) || die "No jobs found in $CONF_FILE" 64

  JOBS=()
  for (( idx=0; idx<total; idx+=1 )); do
    JOBS+=("$(yq eval -o=json -I=0 ".jobs[$idx]" "$CONF_FILE")")
  done
  TOTAL_JOBS="$total"
}

# list_dry_run_files: enumerate note/image files for dry-run reporting
list_dry_run_files() {
  local input_path="$1"
  find "$input_path" -maxdepth 3 -type f \( -name '*.note' -o -name '*.spd' -o -name '*.pdf' -o -name '*.png' -o -name '*.jpg' \) -print 2>/dev/null
}

# emit_dry_run_listing: pretty-print discovered files for dry-run
emit_dry_run_listing() {
  local input_path="$1"
  if [[ -d "$input_path" ]]; then
    echo "[dry-run] Input directory contains:"
    local -a dry_files=()
    while IFS= read -r file; do
      dry_files+=("$file")
    done < <(list_dry_run_files "$input_path")
    if (( ${#dry_files[@]} == 0 )); then
      echo "    (no note/image files discovered)"
    else
      for file in "${dry_files[@]}"; do
        echo "    - $file"
      done
    fi
  else
    echo "[dry-run] Input file: $input_path"
  fi
}

# summarise_job: echo the resolved inputs for a single job
summarise_job() {
  local name="$1" input="$2" output="$3" cfg="$4" model="$5" level="$6" force="$7" progress="$8"
  echo "sn2md job: ${name:-unnamed}"
  echo "  input : $input"
  echo "  output: $output"
  if [[ -n "$cfg" && "$cfg" != "null" ]]; then
    echo "  config: $cfg"
    echo "  model : (from config)"
    echo "  level : (from config)"
    echo "  force : (from config)"
    echo "  progress: (from config)"
  else
    echo "  config: (none)"
    echo "  model : $model"
    echo "  level : $level"
    echo "  force : $force"
    echo "  progress: $progress"
  fi
}

# run_job: execute one job with live logging streamed directly to stdout
run_job() {
  local idx="$1" job_json="$2"
  local job_status=0

  echo "${C_BOLD}${C_CYAN}[job $idx]${C_RESET} ${C_DIM}starting…${C_RESET}"

  local name in_path out_path cfg_path env_file_job force progress level model
  name="$(yq eval -r '.name // ""' - <<<"$job_json")"
  in_path="$(yq eval -r '.input // ""' - <<<"$job_json")"
  out_path="$(yq eval -r '.output // ""' - <<<"$job_json")"
  cfg_path="$(yq eval -r '.config // ""' - <<<"$job_json")"
  env_file_job="$(yq eval -r '.env_file // ""' - <<<"$job_json")"
  force="$(yq eval -r '.flags.force // ""' - <<<"$job_json")"
  progress="$(yq eval -r '.flags.progress // ""' - <<<"$job_json")"
  level="$(yq eval -r '.flags.level // ""' - <<<"$job_json")"
  model="$(yq eval -r '.flags.model // ""' - <<<"$job_json")"

  local -a job_extra_args
  job_extra_args=("${DEF_EXTRA_ARGS[@]}")
  while IFS= read -r arg; do
    [[ -n "$arg" ]] && job_extra_args+=("$arg")
  done < <(yq eval -r '.extra_args // [] | .[]' - <<<"$job_json")

  [[ -z "$in_path" || "$in_path" == "null" ]] && in_path="$DEF_INPUT"
  [[ -z "$out_path" || "$out_path" == "null" ]] && out_path="$DEF_OUTPUT"
  [[ -z "$env_file_job" || "$env_file_job" == "null" ]] && env_file_job="$DEF_ENV_FILE"
  [[ -z "$force" || "$force" == "null" ]] && force="$DEF_FORCE"
  [[ -z "$progress" || "$progress" == "null" ]] && progress="$DEF_PROGRESS"
  [[ -z "$level" || "$level" == "null" ]] && level="$DEF_LEVEL"
  [[ -z "$model" || "$model" == "null" ]] && model="$DEF_MODEL"

  in_path="$(tilde_expand "$(trim "$in_path")")"
  out_path="$(tilde_expand "$(trim "$out_path")")"
  cfg_path="$(tilde_expand "$(trim "$cfg_path")")"
  env_file_job="$(tilde_expand "$(trim "$env_file_job")")"

  if [[ -z "$in_path" ]]; then
    echo "Input missing after defaults (job='${name:-unnamed}')" >&2
    job_status=1
  elif [[ ! -e "$in_path" ]]; then
    echo "Input path not found: $in_path (job='${name:-unnamed}')" >&2
    job_status=1
  elif [[ -n "$cfg_path" && "$cfg_path" != "null" && ! -r "$cfg_path" ]]; then
    echo "Config not readable: $cfg_path (job='${name:-unnamed}')" >&2
    job_status=1
  elif [[ -z "$out_path" ]]; then
    echo "Output missing after defaults (job='${name:-unnamed}')" >&2
    job_status=1
  fi

  if (( job_status == 0 )); then
    if ! $DRY_RUN; then
      mkdir -p "$out_path"
    fi

    while IFS= read -r line; do
      echo "$line"
    done < <(summarise_job "$name" "$in_path" "$out_path" "$cfg_path" "$model" "$level" "$force" "$progress")

    local -a sn_args
    sn_args=(-o "$out_path")
    if [[ -n "$cfg_path" && "$cfg_path" != "null" ]]; then
      sn_args+=(-c "$cfg_path")
    else
      sn_args+=(-m "$model" -l "$level")
      [[ "$force" == "true" ]] && sn_args+=("--force")
      if [[ "$progress" == "true" ]]; then
        sn_args+=("--progress")
      else
        sn_args+=("--no-progress")
      fi
      sn_args+=("${job_extra_args[@]}" "${USER_ARGS[@]}")
    fi

    if [[ -n "$env_file_job" && -r "$env_file_job" ]]; then
      set -o allexport
      source "$env_file_job"
      set +o allexport
    fi

    if $DRY_RUN; then
      local preview
      preview="$(printf '%q ' "$SN2MD_CMD" "${sn_args[@]}" directory "$in_path")"
      preview="${preview% }"
      echo "[dry-run] Would run: $preview"
      while IFS= read -r line; do
        echo "$line"
      done < <(emit_dry_run_listing "$in_path")
      echo "[dry-run] Output would be written under: $out_path"
    else
      if "$SN2MD_CMD" "${sn_args[@]}" directory "$in_path"; then
        job_status=0
      else
        job_status=$?
      fi
    fi
  fi

  if (( job_status == 0 )); then
    echo "${C_BOLD}${C_CYAN}[job $idx]${C_RESET} ${C_GREEN}SUCCESS${C_RESET}"
  else
    echo "${C_BOLD}${C_CYAN}[job $idx]${C_RESET} ${C_RED}FAILED${C_RESET}"
  fi

  return "$job_status"
}

# run_all_jobs: fan out jobs with bounded parallelism and tally results
run_all_jobs() {
  typeset -a pids=()
  typeset -A pid_status=()
  local ok=0 err=0 idx=0

  for job in "${JOBS[@]}"; do
    (( ++idx ))
    ( run_job "$idx" "$job" ) &
    pids+=("$!")

    while (( ${#pids[@]} >= JOBS_LIMIT )); do
      wait "${pids[1]}" && pid_status["${pids[1]}"]=0 || pid_status["${pids[1]}"]=1
      pids=("${pids[@]:1}")
    done
  done

  for pid in "${pids[@]}"; do
    wait "$pid" && pid_status["$pid"]=0 || pid_status["$pid"]=1
  done

  for p in "${(@k)pid_status}"; do
    if (( pid_status[$p] == 0 )); then
      (( ok += 1 ))
    else
      (( err += 1 ))
    fi
  done

  if (( err == 0 )); then
    echo "${C_BOLD}${C_GREEN}All done.${C_RESET} total=$TOTAL_JOBS ok=$ok err=$err"
  else
    echo "${C_BOLD}${C_YELLOW}Completed with errors.${C_RESET} total=$TOTAL_JOBS ok=$ok err=$err"
  fi
  return "$err"
}

# main: orchestrate argument parsing, setup, config loading, and job execution
main() {
  parse_args "$@"
  init_colors

  if $SETUP; then
    bootstrap_sn2md
    discover_sn2md
    if [[ -z "$SN2MD_CMD" ]]; then
      die "sn2md installation failed; ensure uv is available and retry --setup."
    fi
    echo "${C_BOLD}${C_GREEN}sn2md setup complete:${C_RESET} $SN2MD_CMD"
    exit 0
  fi

  require_command "yq" "Try: brew install yq"

  discover_sn2md
  if [[ -z "$SN2MD_CMD" ]]; then
    die "sn2md command not found. Run ./sn2md-batches.sh --setup or install sn2md and set SN2MD_EXEC."
  fi

  load_defaults
  load_jobs

  echo "${C_BOLD}${C_BLUE}sn2md-batches:${C_RESET} jobs=$TOTAL_JOBS parallel=$JOBS_LIMIT config=$CONF_FILE"
  run_all_jobs
}

main "$@"
