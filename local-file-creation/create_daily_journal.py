import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytz
import logging

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get the directory of the script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Get the root directory (parent of the script directory)
root_dir = os.path.dirname(script_dir)

# Load environment variables from the .env file in the root directory
load_dotenv(os.path.join(root_dir, '.env'))

# --- Timezone Configuration ---
timezone_str = os.getenv("SYSTEM_TIMEZONE", "US/Eastern")
logger.info(f"Using timezone: {timezone_str}")

def find_daily_folder(base_path):
    for item in os.listdir(base_path):
        if item.endswith("_Daily") and os.path.isdir(os.path.join(base_path, item)):
            return item
    raise FileNotFoundError("Could not find a folder ending with '_Daily'")

def fetch_last_journal_date(journal_path):
    journal_files = [f for f in os.listdir(journal_path) if f.endswith(".md")]
    if not journal_files:
        return None
    return max(journal_files).split('.md')[0]

def create_journal_file(file_path):
    # Define timezone using environment variable
    system_tz = pytz.timezone(timezone_str)

    # Get the current time in system timezone
    now_system = datetime.now(system_tz)
    # Calculate the time for the next day
    next_day = now_system + timedelta(days=1)
    
    # Format the date for the journal title
    formatted_date = f"{next_day.strftime('%b')} {next_day.day}, {next_day.strftime('%Y')}"  # e.g., Jun 1, 2024

    # Create the file name
    file_name = f"{formatted_date}.md"
    full_file_path = os.path.join(file_path, file_name)

    # Fetch the last journal date
    last_journal_date = fetch_last_journal_date(file_path)

    # Check if the last journal date matches the formatted date
    if last_journal_date == formatted_date:
        print(f"Journal file for '{formatted_date}' already exists. No new file created.")
        return

    # Check if the file already exists
    if os.path.exists(full_file_path):
        print(f"File '{file_name}' already exists. Skipping creation.")
        return

    # Create the file with content
    try:
        with open(full_file_path, 'w') as file:
                pass  # This creates an empty file
        print(f"Successfully created file '{file_name}'")
    except IOError as e:
        print(f"Error creating file: {e}")

def main():
    # Get the base path from environment variable
    base_path = os.getenv('OBSIDIAN_VAULT_BASE_PATH')
    if not base_path:
        print("Error: OBSIDIAN_VAULT_BASE_PATH environment variable not set")
        sys.exit(1)

    try:
        daily_folder = find_daily_folder(base_path)
        journal_path = os.path.join(base_path, daily_folder, "_Journal")
        if not os.path.exists(journal_path):
            raise FileNotFoundError("'_Journal' subfolder not found")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    create_journal_file(journal_path)

if __name__ == "__main__":
    main()