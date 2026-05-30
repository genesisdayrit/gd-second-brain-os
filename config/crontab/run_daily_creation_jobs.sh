#!/usr/bin/env bash

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
CRON_LOGS_PATH="$PROJECT_ROOT/cron_logs"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing Python executable at $PYTHON_BIN"
  exit 1
fi

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

mkdir -p "$CRON_LOGS_PATH"

success_count=0
failure_count=0
declare -a failed_jobs=()

run_job() {
  local job_name="$1"
  local log_name="$2"
  shift 2

  echo "==> Running: $job_name"
  if "$@" >> "$CRON_LOGS_PATH/$log_name" 2>&1; then
    ((success_count+=1))
    echo "    OK"
  else
    ((failure_count+=1))
    failed_jobs+=("$job_name (log: $CRON_LOGS_PATH/$log_name)")
    echo "    FAILED"
  fi
}

run_job "create_daily_journal.py --today" "create_daily_journal.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/create_daily_journal.py" "--today"
run_job "create_daily_action_page.py --today" "create_daily_action.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/create_daily_action_page.py" "--today"

echo
echo "Daily creation run finished. Success: $success_count, Failed: $failure_count"

if (( failure_count > 0 )); then
  echo "Failed jobs:"
  for failed_job in "${failed_jobs[@]}"; do
    echo "  - $failed_job"
  done
  exit 1
fi
