import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import logging

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Timezone Configuration ---
timezone_str = os.getenv("SYSTEM_TIMEZONE", "US/Eastern")
logger.info(f"Using timezone: {timezone_str}")

def get_day_of_week():
    """Returns the full weekday name for today."""
    today = datetime.now(pytz.timezone(timezone_str))
    return today.strftime('%A')

def get_week_ending_sunday():
    """Returns the next Sunday (or today if already Sunday)."""
    today = datetime.now(pytz.timezone(timezone_str))
    days_until_sunday = (6 - today.weekday()) % 7  # Sunday = 6
    week_ending = today + timedelta(days=days_until_sunday)
    return week_ending.strftime('%Y-%m-%d')  # Return in YYYY-MM-DD format

def get_week_ending_filenames():
    """Returns the filenames based on the week-ending Sunday date."""
    week_ending_sunday = get_week_ending_sunday()
    return {
        "week_ending": f"Week-Ending-{week_ending_sunday}",
        "weekly_map": f"Weekly Map {week_ending_sunday}"
    }

def get_cycle_date_range():
    """Finds the Wednesday-Tuesday range for the given date."""
    today = datetime.now(pytz.timezone(timezone_str))
    
    # Find the most recent Wednesday
    days_since_wednesday = (today.weekday() - 2) % 7  # Wednesday = 2
    cycle_start = today - timedelta(days=days_since_wednesday)

    # Find the next Tuesday
    cycle_end = cycle_start + timedelta(days=6)

    # Format as 'MMM. DD - MMM. DD, YYYY'
    return f"{cycle_start.strftime('%b. %d')} - {cycle_end.strftime('%b. %d, %Y')}"

# Example outputs:
print(get_day_of_week())  # "Sunday"
print(get_week_ending_sunday())  # "2025-02-09"
print(get_week_ending_filenames())  
# {"week_ending": "Week-Ending-2025-02-09", "weekly_map": "Weekly Map 2025-02-09"}
print(get_cycle_date_range())  # "Feb. 05 - Feb. 11, 2025"

