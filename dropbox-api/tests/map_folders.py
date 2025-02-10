import os
import redis
import dropbox
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Load Environment Variables ---
load_dotenv()

# --- Timezone Configuration ---
# Use the TIMEZONE environment variable if available, otherwise default to US/Eastern.
timezone_str = os.getenv("SYSTEM_TIMEZONE", "US/Eastern")
logger.info(f"Using timezone: {timezone_str}")

# --- Redis Configuration ---
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# --- Connect to Redis ---
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# --- Function to Get Dropbox Access Token from Redis ---
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        logger.error("Dropbox access token not found in Redis.")
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    logger.info("Dropbox access token retrieved from Redis.")
    return access_token

# --- Initialize Dropbox Client ---
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
logger.info("Dropbox client initialized.")

# --- Date Functions (using timezone from environment) ---
def get_day_of_week():
    """Returns the full weekday name for today."""
    today = datetime.now(pytz.timezone(timezone_str))
    day = today.strftime('%A')
    logger.debug(f"Day of week: {day}")
    return day

def get_week_ending_sunday():
    """Returns the next Sunday (or today if already Sunday) in YYYY-MM-DD format."""
    today = datetime.now(pytz.timezone(timezone_str))
    days_until_sunday = (6 - today.weekday()) % 7  # Sunday = 6
    week_ending = today + timedelta(days=days_until_sunday)
    week_ending_str = week_ending.strftime('%Y-%m-%d')
    logger.debug(f"Week ending Sunday: {week_ending_str}")
    return week_ending_str

def get_week_ending_filenames():
    """Returns filenames based on the week-ending Sunday date."""
    week_ending_sunday = get_week_ending_sunday()
    filenames = {
        "week_ending": f"Week-Ending-{week_ending_sunday}",
        "weekly_map": f"Weekly Map {week_ending_sunday}"
    }
    logger.debug(f"Week ending filenames: {filenames}")
    return filenames

def get_cycle_date_range():
    """Finds the Wednesday-Tuesday range for the given date and formats it as 'MMM. DD - MMM. DD, YYYY'."""
    today = datetime.now(pytz.timezone(timezone_str))
    days_since_wednesday = (today.weekday() - 2) % 7  # Wednesday = 2
    cycle_start = today - timedelta(days=days_since_wednesday)
    cycle_end = cycle_start + timedelta(days=6)
    cycle_range = f"{cycle_start.strftime('%b. %d')} - {cycle_end.strftime('%b. %d, %Y')}"
    logger.debug(f"Cycle date range: {cycle_range}")
    return cycle_range

def get_weekly_newsletter_filename():
    """
    Returns the newsletter filename in the format:
    'Weekly Newsletter Feb. 02, 2025'
    based on the week-ending Sunday date.
    """
    week_end_date_str = get_week_ending_sunday()  # "YYYY-MM-DD"
    week_end_date = datetime.strptime(week_end_date_str, '%Y-%m-%d')
    newsletter_filename = week_end_date.strftime("Weekly Newsletter %b. %d, %Y")
    logger.debug(f"Weekly newsletter filename: {newsletter_filename}")
    return newsletter_filename

def get_today_date():
    """Returns today's date in YYYY-MM-DD format."""
    today = datetime.now(pytz.timezone(timezone_str))
    today_str = today.strftime('%Y-%m-%d')
    logger.debug(f"Today's date: {today_str}")
    return today_str

# --- Compute Dynamic Date Variables Once ---
cycle_date_range = get_cycle_date_range()
weekly_map = get_week_ending_filenames()["weekly_map"]
weekly_newsletter = get_weekly_newsletter_filename()
week_ending = get_week_ending_sunday()
today_date = get_today_date()
daily_action_string = "DA " + today_date

logger.info(f"Computed cycle date range: {cycle_date_range}")
logger.info(f"Computed weekly map: {weekly_map}")
logger.info(f"Computed weekly newsletter: {weekly_newsletter}")
logger.info(f"Computed week ending: {week_ending}")
logger.info(f"Computed today's date: {today_date}")

# --- Build Mappings with Actual Values ---
mappings = [
    # 1. Week Ending (parent: _Weekly, target: _Weeks)
    {
        "parent_folder": "_Weekly",
        "target_folder": "_Weeks",
        "target_file_string": week_ending
    },
    # 2. Weekly Maps (parent: _Weekly, target: _Weekly-Maps)
    {
        "parent_folder": "_Weekly",
        "target_folder": "_Weekly-Maps",
        "target_file_string": weekly_map
    },
    # 3. Cycles (parent: _Cycles, target: _Weekly-Cycles)
    {
        "parent_folder": "_Cycles",
        "target_folder": "_Weekly-Cycles",
        "target_file_string": cycle_date_range
    },
    # 4. Weekly Health Review (parent: _Weekly, target: _Weekly-Health-Review)
    {
        "parent_folder": "_Weekly",
        "target_folder": "_Weekly-Health-Review",
        "target_file_string": cycle_date_range
    },
    # 5. Newsletter (parent: _Weekly, target: _Newsletters)
    {
        "parent_folder": "_Weekly",
        "target_folder": "_Newsletters",
        "target_file_string": weekly_newsletter
    },
    # 6. Daily Action (parent: _Daily, target: _Daily-Action)
    {
        "parent_folder": "_Daily",
        "target_folder": "_Daily-Action",
        "target_file_string": daily_action_string
    }
]

# --- Helper Function for Pagination ---
def list_all_entries(base_path):
    """Lists all entries in a folder, handling pagination."""
    entries = []
    try:
        response = dbx.files_list_folder(base_path)
        entries.extend(response.entries)
        while response.has_more:
            response = dbx.files_list_folder_continue(response.cursor)
            entries.extend(response.entries)
        logger.debug(f"Total entries retrieved from {base_path}: {len(entries)}")
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Error fetching folder list from {base_path}: {e}")
    return entries

# --- Helper Functions for Folder and File Lookup ---
def find_folder_in_path(base_path, search_term):
    """
    Searches for a folder within base_path whose name contains the search_term (case-insensitive).
    Returns the folder's path if found.
    """
    logger.info(f"Searching for folder in '{base_path}' with term '{search_term}'.")
    entries = list_all_entries(base_path)
    for entry in entries:
        if isinstance(entry, dropbox.files.FolderMetadata):
            folder_name = entry.name
            if search_term.lower() in folder_name.lower():
                logger.info(f"Match found: {folder_name} in {base_path}")
                return entry.path_lower
    logger.warning(f"No folder containing '{search_term}' found in '{base_path}'.")
    return None

def lookup_file_in_folder(folder_path, file_template):
    """
    Searches for a file within folder_path whose name contains file_template (case-insensitive).
    Returns the file's path if found.
    """
    logger.info(f"Looking up file in '{folder_path}' with template '{file_template}'.")
    entries = list_all_entries(folder_path)
    for entry in entries:
        if isinstance(entry, dropbox.files.FileMetadata):
            file_name = entry.name
            if file_template.lower() in file_name.lower():
                logger.info(f"Match found: {file_name}")
                return entry.path_lower
    logger.warning(f"No file containing '{file_template}' found in '{folder_path}'.")
    return None

def process_mapping(mapping):
    """
    Processes a single mapping object:
      1. Finds the parent folder in the vault.
      2. Searches within that parent for the target subfolder.
      3. Uses the pre-computed target_file_string.
      4. Looks up the file in the target folder using a contains search.
    Returns a dictionary with mapping details and the found file path.
    """
    file_string = mapping["target_file_string"].lower()
    logger.info(f"Using file search string: {file_string}")

    # Find the parent folder (search from the vault root)
    vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
    parent_folder = find_folder_in_path(vault_path, mapping["parent_folder"])
    if not parent_folder:
        logger.error(f"Parent folder containing '{mapping['parent_folder']}' not found in vault '{vault_path}'.")
        return None

    # Find the target folder within the parent folder
    target_folder = find_folder_in_path(parent_folder, mapping["target_folder"])
    if not target_folder:
        logger.error(f"Target folder containing '{mapping['target_folder']}' not found within parent folder '{mapping['parent_folder']}'.")
        return None

    # Look up the file in the target folder using a contains search
    file_path = lookup_file_in_folder(target_folder, file_string)
    return {
        "parent_folder": mapping["parent_folder"],
        "target_folder": mapping["target_folder"],
        "dynamic_file_string": file_string,
        "file_path": file_path
    }

def main():
    results = []
    for mapping in mappings:
        logger.info(f"Processing mapping: {mapping}")
        result = process_mapping(mapping)
        if result:
            results.append(result)
    logger.info("Mapping results:")
    for res in results:
        logger.info(res)

if __name__ == "__main__":
    main()

