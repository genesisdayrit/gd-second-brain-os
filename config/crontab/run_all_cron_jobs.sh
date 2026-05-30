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

run_job "refresh_token_to_redis.py" "refresh_token_to_redis.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/config/refresh_token_to_redis.py"
run_job "create_weeks.py" "create_weeks.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/create_weeks.py"
run_job "create_newsletter_page.py" "create_newsletter.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/create_newsletter_page.py"
run_job "create_new_cycle_page.py" "create_new_cycle.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/create_new_cycle_page.py"
run_job "create_weekly_health_review_page.py" "create_weekly_health_review.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/create_weekly_health_review_page.py"
run_job "create_weekly_map.py" "create_weekly_map.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/create_weekly_map.py"
run_job "create_daily_journal.py" "create_daily_journal.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/create_daily_journal.py"
run_job "create_daily_action_page.py" "create_daily_action.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/create_daily_action_page.py"
run_job "update_daily_properties.py" "update_daily_properties.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/workflows/update_daily_properties.py"
run_job "add_daily_review_section.py" "add_daily_review_section.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/file-creation/add_daily_review_section.py"
run_job "daily_prep.py" "daily_prep.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/workflows/daily_prep.py"
run_job "daily_reflection.py" "daily_reflection.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/workflows/daily_reflection.py"
run_job "essay_ideas_from_journal.py" "essay_ideas_from_journal.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/workflows/essay_ideas_from_journal.py"
run_job "update_modified_files_today.py" "folder_journal.log" "$PYTHON_BIN" "$PROJECT_ROOT/dropbox-api/relate-files/update_modified_files_today.py"
run_job "sync_yt_and_knowledge_hub.py" "sync_yt_and_knowledge_hub.log" "$PYTHON_BIN" "$PROJECT_ROOT/notion-api/knowledge-hub/sync_yt_and_knowledge_hub.py"
run_job "refresh_redis_token.py" "refresh_redis_token.log" "$PYTHON_BIN" "$PROJECT_ROOT/gmail/config/refresh_redis_token.py"

echo
echo "Backfill finished. Success: $success_count, Failed: $failure_count"

if (( failure_count > 0 )); then
  echo "Failed jobs:"
  for failed_job in "${failed_jobs[@]}"; do
    echo "  - $failed_job"
  done
  exit 1
fi
