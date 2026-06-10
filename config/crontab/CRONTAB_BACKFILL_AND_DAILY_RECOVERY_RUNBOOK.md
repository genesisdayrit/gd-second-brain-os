# Crontab Backfill And Daily Recovery Runbook

This project includes helper scripts to manually run cron jobs after downtime.

## From repo root

```bash
cd /Users/Genesis/repos/gd-second-brain-os
```

## 1) Run all cron jobs once (full backfill)

Runs all configured cron scripts in sequence.  
`refresh_token_to_redis.py` runs first.

```bash
./config/crontab/run_all_cron_jobs.sh
```

## 2) Run daily creation flow

Runs the daily scripts in this sequence:
1. `create_daily_journal.py`
2. `create_daily_action_page.py`
3. `update_daily_properties.py`

Any arguments passed to the script are forwarded to each job. Run without
arguments for the upcoming day, or pass `--today` to target today.

```bash
# Upcoming day
./config/crontab/run_daily_creation_jobs.sh

# Today only
./config/crontab/run_daily_creation_jobs.sh --today
```

## Check logs

All output is appended to files in `cron_logs/`.

```bash
ls cron_logs
```

Useful quick checks:

```bash
tail -n 50 cron_logs/create_daily_journal.log
tail -n 50 cron_logs/create_daily_action.log
tail -n 50 cron_logs/update_daily_properties.log
tail -n 50 cron_logs/refresh_token_to_redis.log
```
