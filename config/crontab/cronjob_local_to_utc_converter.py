#!/usr/bin/env python3
import os
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo       # Python 3.9+
from dotenv import load_dotenv      # pip install python-dotenv

# ── CONFIG (update as needed) ─────────────────────────────────────────────
TARGET_HOUR       = 12              # local hour (24-hr clock)
TARGET_MINUTE     = 30              # local minute
TARGET_LOCAL_DOW  = 6              # 0–7 cron-style (0 or 7=Sun, 1=Mon … 6=Sat)
# ──────────────────────────────────────────────────────────────────────────

# Load your timezone from .env
load_dotenv()
SYSTEM_TIMEZONE = os.getenv("SYSTEM_TIMEZONE")
if not SYSTEM_TIMEZONE:
    raise RuntimeError("Please set SYSTEM_TIMEZONE in your .env")

# Convert cron-style DOW → Python weekday (Mon=0…Sun=6)
py_target_dow = (TARGET_LOCAL_DOW - 1) % 7

# Find the next date (today or later) matching that local weekday
today       = date.today()
days_ahead  = (py_target_dow - today.weekday() + 7) % 7
target_date = today + timedelta(days=days_ahead)

# Build local datetime and convert to UTC
local_dt = datetime.combine(
    target_date,
    time(TARGET_HOUR, TARGET_MINUTE),
    tzinfo=ZoneInfo(SYSTEM_TIMEZONE)
)
utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

# Compute UTC cron-style DOW (0=Sun…6=Sat)
cron_dow = (utc_dt.weekday() + 1) % 7

# Print the five-field cron spec
print(
    f"{utc_dt.minute} {utc_dt.hour} * * {cron_dow}  "
    f"# runs at {TARGET_HOUR:02d}:{TARGET_MINUTE:02d} "
    f"(local dow={TARGET_LOCAL_DOW}) in {SYSTEM_TIMEZONE}"
)
