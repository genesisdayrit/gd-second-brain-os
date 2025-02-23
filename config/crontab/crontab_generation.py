import os
import pyperclip

# Define the environment variables
PROJECT_REPO_PATH = os.getenv("PROJECT_REPO_PATH", "/home/ubuntu/repos/gd-second-brain-os")
VENV_PATH = f"{PROJECT_REPO_PATH}/venv/bin/python"
CONFIG_PATH = f"{PROJECT_REPO_PATH}/config"
DROPBOX_API_PATH = f"{PROJECT_REPO_PATH}/dropbox-api"
CRON_LOGS_PATH = f"{PROJECT_REPO_PATH}/cron_logs"
NOTION_API_PATH = f"{PROJECT_REPO_PATH}/notion-api/knowledge-hub"
GMAIL_API_PATH = f"{PROJECT_REPO_PATH}/gmail/config"

# Define the cron jobs with placeholders
cron_jobs = f"""
# Run create_weeks_page.py every Monday at 6:00 AM UTC (1:00 AM CT)
0 6 * * 1 {CONFIG_PATH}/dropbox_file_creation.sh create_weeks.py >> {CRON_LOGS_PATH}/create_weeks.log 2>&1

# Run create_newsletter_page.py every Friday at 6:30 AM UTC (1:30 AM CT)
30 6 * * 5 {CONFIG_PATH}/dropbox_file_creation.sh create_newsletter_page.py >> {CRON_LOGS_PATH}/create_newsletter.log 2>&1

# Run create_new_cycle_page.py every Tuesday at 8:30 AM UTC (3:30 AM CT)
30 8 * * 2 {CONFIG_PATH}/dropbox_file_creation.sh create_new_cycle_page.py >> {CRON_LOGS_PATH}/create_new_cycle.log 2>&1

# Run create_weekly_health_review_page.py every Tuesday at 9:00 AM UTC (4:00 AM CT)
0 9 * * 2 {CONFIG_PATH}/dropbox_file_creation.sh create_weekly_health_review_page.py >> {CRON_LOGS_PATH}/create_weekly_health_review.log 2>&1

# Run create_weekly_map.py every Thursday at 6:00 AM UTC (1:00 AM CT)
0 6 * * 4 {CONFIG_PATH}/dropbox_file_creation.sh create_weekly_map.py >> {CRON_LOGS_PATH}/create_weekly_map.log 2>&1

# Run create_daily_journal_page.py daily at 1:00 AM UTC (9:00 PM ET)
0 1 * * * {CONFIG_PATH}/dropbox_file_creation.sh create_daily_journal.py >> {CRON_LOGS_PATH}/create_daily_journal.log 2>&1

# Run create_daily_action_page.py daily at 1:05 AM UTC (9:05 PM ET)
5 1 * * * {CONFIG_PATH}/dropbox_file_creation.sh create_daily_action_page.py >> {CRON_LOGS_PATH}/create_daily_action.log 2>&1

# Run update_daily_properties.py 5 minutes after the daily action note is created (1:10 AM UTC)
10 1 * * * {VENV_PATH} {DROPBOX_API_PATH}/workflows/update_daily_properties.py >> {CRON_LOGS_PATH}/update_daily_properties.log 2>&1

# Run add_daily_review_section.py daily at 8:00 PM UTC (3:00 PM ET)
0 20 * * * {CONFIG_PATH}/dropbox_file_creation.sh add_daily_review_section.py >> {CRON_LOGS_PATH}/add_daily_review_section.log 2>&1

# Run daily_prep.py daily at 5:30 PM UTC
30 17 * * * {VENV_PATH} {DROPBOX_API_PATH}/workflows/daily_prep.py >> {CRON_LOGS_PATH}/daily_prep.log 2>&1

# Run daily_reflection.py daily at 3:30 AM UTC next day
30 3 * * * {VENV_PATH} {DROPBOX_API_PATH}/workflows/daily_reflection.py >> {CRON_LOGS_PATH}/daily_reflection.log 2>&1

# Run essay_ideas_from_journal.py daily at 1:25 AM UTC next day
25 1 * * * {VENV_PATH} {DROPBOX_API_PATH}/workflows/essay_ideas_from_journal.py >> {CRON_LOGS_PATH}/essay_ideas_from_journal.log 2>&1

# Run Dropbox 'folder-journal-relations' script daily at 12:05 AM Eastern
5 0 * * * {VENV_PATH} {DROPBOX_API_PATH}/relate-files/update_modified_files_today.py >> {CRON_LOGS_PATH}/folder_journal.log 2>&1

# Refreshes Dropbox access token every 3 hours and stores it in Redis.
0 */3 * * * {VENV_PATH} {DROPBOX_API_PATH}/config/refresh_token_to_redis.py >> {CRON_LOGS_PATH}/refresh_token_to_redis.log 2>&1

# Run sync_knowledge_hub.py every 5 minutes to sync Notion Knowledge Hub with Dropbox
*/5 * * * * {VENV_PATH} {NOTION_API_PATH}/sync_yt_and_knowledge_hub.py >> {CRON_LOGS_PATH}/sync_yt_and_knowledge_hub.log 2>&1

# Refresh Gmail API token every 55 minutes to ensure it stays valid
*/55 * * * * {VENV_PATH} {GMAIL_API_PATH}/refresh_redis_token.py >> {CRON_LOGS_PATH}/refresh_redis_token.log 2>&1
"""

# Output to console
print("Generated Crontab Configuration:")
print(cron_jobs)

# Copy to clipboard
pyperclip.copy(cron_jobs)
print("\nCrontab configuration copied to clipboard!")
