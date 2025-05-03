#!/usr/bin/env python3
import os
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo     # Python 3.9+
from dotenv import load_dotenv    # pip install python-dotenv

# ── CONFIG (update or replace with CLI args) ─────────────────────────────────
# Your UTC cron fields:
SOURCE_UTC_HOUR   = 20       # 0–23
SOURCE_UTC_MINUTE = 0        # 0–59
SOURCE_CRON_DOW   = 2        # 0=Sun,1=Mon…6=Sat

# The timezone you want to convert into:
TARGET_TIMEZONE = "America/New_York"  # e.g. "America/New_York", "Europe/London", etc.
# TARGET_TIMEZONE = "Asia/Kuala_Lumpur"  # e.g. "America/New_York", "Europe/London", etc.
# ──────────────────────────────────────────────────────────────────────────────

# (Optionally) load a default TZ from .env
load_dotenv()
TARGET_TIMEZONE = os.getenv("TARGET_TIMEZONE", TARGET_TIMEZONE)

# Convert cron‐style DOW → Python weekday (Mon=0…Sun=6)
py_source_dow = (SOURCE_CRON_DOW - 1) % 7

# Find the next date (today or later) matching that UTC weekday
today_utc   = date.today()
days_ahead  = (py_source_dow - today_utc.weekday() + 7) % 7
utc_date    = today_utc + timedelta(days=days_ahead)

# Build a UTC‐aware datetime
utc_dt = datetime.combine(
    utc_date,
    time(SOURCE_UTC_HOUR, SOURCE_UTC_MINUTE),
    tzinfo=ZoneInfo("UTC")
)

# Convert it to your target timezone
local_dt = utc_dt.astimezone(ZoneInfo(TARGET_TIMEZONE))

# Compute local cron‐style DOW (0=Sun…6=Sat)
local_cron_dow = (local_dt.weekday() + 1) % 7

# Print out your new cron spec
print(
    f"{local_dt.minute} {local_dt.hour} * * {local_cron_dow}  "
    f"# runs at UTC {SOURCE_UTC_HOUR:02d}:{SOURCE_UTC_MINUTE:02d}, "
    f"which is local {local_dt.hour:02d}:{local_dt.minute:02d} "
    f"on DOW={local_cron_dow} in {TARGET_TIMEZONE}"
)
