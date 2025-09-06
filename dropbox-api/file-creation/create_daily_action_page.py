import os
import dropbox
from datetime import datetime, timedelta
import pytz
import redis
from dotenv import load_dotenv
from pathlib import Path
import logging
import re
import yaml

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

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')  # Default to 'localhost' if not set
redis_port = int(os.getenv('REDIS_PORT', 6379))    # Default to 6379 if not set
redis_password = os.getenv('REDIS_PASSWORD', None)  # Default to None if not set

# Connect to Redis using the environment variables
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Function to get the Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Get the PROJECT_ROOT_PATH
PROJECT_ROOT_PATH = os.getenv('PROJECT_ROOT_PATH')

# Ensure the PROJECT_ROOT_PATH is set
if not PROJECT_ROOT_PATH:
    raise EnvironmentError("Error: PROJECT_ROOT_PATH environment variable not set")

# Construct the path to the .env file and load it
env_path = Path(PROJECT_ROOT_PATH) / '.env'
load_dotenv(dotenv_path=env_path)

# Retrieve the Dropbox access token from Redis
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()

# Initialize Dropbox client using the token from Redis
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# --- Date Utility Functions ---
def get_tomorrow():
    """Return tomorrow's datetime object in the configured timezone."""
    return datetime.now(pytz.timezone(timezone_str)) + timedelta(days=1)

def get_tomorrow_journal_filename():
    """Format tomorrow's date to match journal filename format: 'MMM D, YYYY'"""
    tomorrow = get_tomorrow()
    try:
        return tomorrow.strftime('%b %-d, %Y')  # Linux/macOS
    except ValueError:
        return tomorrow.strftime('%b %#d, %Y')  # Windows

def get_cycle_date_range():
    """Get weekly cycle date range for tomorrow's date."""
    tomorrow = get_tomorrow()
    # Wednesday = 2; compute days since last Wednesday based on tomorrow
    days_since_wednesday = (tomorrow.weekday() - 2) % 7
    cycle_start = tomorrow - timedelta(days=days_since_wednesday)
    cycle_end = cycle_start + timedelta(days=6)
    return f"{cycle_start.strftime('%b. %d')} - {cycle_end.strftime('%b. %d, %Y')}"

# --- File Discovery Utility Functions ---
def list_all_entries(base_path):
    """Lists all entries in a folder, handling pagination."""
    entries = []
    try:
        response = dbx.files_list_folder(base_path)
        entries.extend(response.entries)
        while response.has_more:
            response = dbx.files_list_folder_continue(response.cursor)
            entries.extend(response.entries)
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Error fetching folder list from {base_path}: {e}")
    return entries

def find_folder_in_path(base_path, search_term):
    """
    Searches for a folder within base_path whose name contains search_term (case-insensitive).
    Returns the folder's path.
    """
    logger.info(f"Searching for folder in '{base_path}' containing '{search_term}'.")
    entries = list_all_entries(base_path)
    for entry in entries:
        if isinstance(entry, dropbox.files.FolderMetadata):
            if search_term.lower() in entry.name.lower():
                logger.info(f"Folder match found: {entry.name}")
                return entry.path_lower
    logger.warning(f"No folder containing '{search_term}' found in '{base_path}'.")
    return None

def lookup_file_in_folder(folder_path, file_template):
    """
    Searches for a file within folder_path whose name contains file_template (case-insensitive).
    Returns a tuple of (file_path, original_file_name) if found.
    """
    logger.info(f"Looking up file in '{folder_path}' with template '{file_template}'.")
    entries = list_all_entries(folder_path)
    for entry in entries:
        if isinstance(entry, dropbox.files.FileMetadata):
            if file_template.lower() in entry.name.lower():
                logger.info(f"File match found: {entry.name}")
                return entry.path_lower, entry.name
    logger.warning(f"No file containing '{file_template}' found in '{folder_path}'.")
    return None, None

def parse_date_range_from_filename(filename, target_date):
    """
    Parse date range from filenames like:
    - "6-Week Cycle (2025.01.15 - 2025.02.25).md"
    - "2-Week Cooling Period (2025.02.26 - 2025.03.11).md"
    
    Returns True if target_date falls within the date range.
    """
    # Pattern to match date ranges in format (yyyy.mm.dd - yyyy.mm.dd)
    pattern = r'\((\d{4}\.\d{2}\.\d{2}) - (\d{4}\.\d{2}\.\d{2})\)'
    match = re.search(pattern, filename)
    
    if not match:
        return False
    
    start_str, end_str = match.groups()
    
    try:
        # Convert yyyy.mm.dd to date objects
        start_date = datetime.strptime(start_str, '%Y.%m.%d').date()
        end_date = datetime.strptime(end_str, '%Y.%m.%d').date()
        
        # Check if target_date falls within the range (inclusive)
        return start_date <= target_date <= end_date
        
    except ValueError as e:
        logger.warning(f"Could not parse dates from filename '{filename}': {e}")
        return False

def get_long_cycle_filename(vault_path):
    """
    Scan the _6-Week-Cycles folder and find which file contains tomorrow's date.
    Returns the filename string that matches tomorrow's date range.
    """
    tomorrow = get_tomorrow().date()
    
    if not vault_path:
        logger.error("Vault path is not provided.")
        return None
    
    # Find the _Cycles parent folder
    cycles_folder = find_folder_in_path(vault_path, "_Cycles")
    if not cycles_folder:
        logger.error("Could not find _Cycles folder in vault.")
        return None
    
    # Find the _6-Week-Cycles subfolder
    six_week_cycles_folder = find_folder_in_path(cycles_folder, "_6-Week-Cycles")
    if not six_week_cycles_folder:
        logger.error("Could not find _6-Week-Cycles folder.")
        return None
    
    # Get all files in the folder
    entries = list_all_entries(six_week_cycles_folder)
    
    for entry in entries:
        if isinstance(entry, dropbox.files.FileMetadata):
            filename = entry.name
            
            # Extract date range from filename
            if parse_date_range_from_filename(filename, tomorrow):
                # Remove .md extension if present
                if filename.lower().endswith('.md'):
                    filename = filename[:-3]
                logger.info(f"Found matching long cycle file: {filename}")
                return filename
    
    logger.warning(f"No long cycle file found containing tomorrow's date: {tomorrow}")
    return None

def find_daily_folder(vault_path):
    """Search for the '_Daily' folder in the specified vault path."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily' in Dropbox")

def find_daily_action_folder(vault_path):
    """Search for the '_Daily-Action' folder inside the specified daily folder."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily-Action"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily-Action' in Dropbox")

# --- Relationship Discovery Functions ---
def find_weekly_cycle_link(vault_path):
    """Find weekly cycle file for tomorrow's date."""
    try:
        # Navigate: vault → _Cycles → _Weekly-Cycles → find file matching cycle_date_range
        cycles_folder = find_folder_in_path(vault_path, "_Cycles")
        if not cycles_folder:
            logger.warning("Could not find _Cycles folder for weekly cycle lookup.")
            return ""
        
        weekly_cycles_folder = find_folder_in_path(cycles_folder, "_Weekly-Cycles")
        if not weekly_cycles_folder:
            logger.warning("Could not find _Weekly-Cycles folder.")
            return ""
        
        cycle_date_range = get_cycle_date_range()
        file_path, file_name = lookup_file_in_folder(weekly_cycles_folder, cycle_date_range)
        
        if file_path and file_name:
            # Remove .md extension if present
            base_name = file_name
            if base_name.lower().endswith('.md'):
                base_name = base_name[:-3]
            return f"[[{base_name}]]"
        else:
            logger.warning(f"No weekly cycle file found for date range: {cycle_date_range}")
            return ""
            
    except Exception as e:
        logger.error(f"Error finding weekly cycle link: {e}")
        return ""

def find_long_cycle_link(vault_path):
    """Find long cycle file for tomorrow's date."""
    try:
        long_cycle_filename = get_long_cycle_filename(vault_path)
        if long_cycle_filename:
            return f"[[{long_cycle_filename}]]"
        else:
            logger.warning("No long cycle file found for tomorrow's date.")
            return ""
    except Exception as e:
        logger.error(f"Error finding long cycle link: {e}")
        return ""

def generate_yaml_properties(vault_path):
    """Generate the three YAML properties with relationship links."""
    # Journal link - simple date formatting (not a list)
    journal_filename = get_tomorrow_journal_filename()
    journal_link = f"[[{journal_filename}]]"
    
    # Weekly cycle link (should be a list)
    weekly_cycle_link = find_weekly_cycle_link(vault_path)
    weekly_cycle_list = [weekly_cycle_link] if weekly_cycle_link else []
    
    # Long cycle link (should be a list)
    long_cycle_link = find_long_cycle_link(vault_path)
    long_cycle_list = [long_cycle_link] if long_cycle_link else []
    
    return {
        'journal': journal_link,
        'weekly_cycle': weekly_cycle_list,
        'long_cycle': long_cycle_list
    }

def create_daily_action_file(daily_action_folder_path, vault_path):
    """Create a new daily action file with YAML properties and structured content."""
    # Get tomorrow's date for filename
    next_day = get_tomorrow()
    
    # Format the file name as "DA YYYY-MM-DD"
    file_name = f"DA {next_day.strftime('%Y-%m-%d')}.md"
    dropbox_file_path = f"{daily_action_folder_path}/{file_name}"

    # Generate YAML properties
    yaml_props = generate_yaml_properties(vault_path)
    
    # Build YAML frontmatter using proper YAML formatting
    yaml_metadata = {
        '_Journal': yaml_props['journal'],
        '_Weekly-Cycle': yaml_props['weekly_cycle'],
        '_Long-Cycle': yaml_props['long_cycle']
    }
    
    yaml_str = yaml.safe_dump(yaml_metadata, default_flow_style=False, sort_keys=False)
    yaml_section = f"---\n{yaml_str}---\n\n"
    
    # Content structure with section prompts and questions
    main_content = (
        "Vision Objective 1:\n"
        "Vision Objective 2:\n"
        "Vision Objective 3:\n\n"
        "One thing that you can do to improve today:\n\n"
        "Mindset Objective:\n"
        "Body Objective:\n"
        "Social Objective:\n\n"
        "Gratitude:\n\n"
        "---\n\n"
        "What is the highest leverage thing that you can do today to move the ball forward on what you need to?\n"
        "If you only had 2 hours to work today, what would you need to get done to move forward towards your goals or master vision?"
    )
    
    # Combine YAML and content
    content = yaml_section + main_content

    try:
        # Check if the file already exists
        dbx.files_get_metadata(dropbox_file_path)
        print(f"Daily action file for '{next_day.strftime('%Y-%m-%d')}' already exists. No new file created.")
    except dropbox.exceptions.ApiError as e:
        if isinstance(e.error, dropbox.files.GetMetadataError):
            print(f"File '{file_name}' does not exist in Dropbox. Creating it now.")
            # Upload the file with the content
            dbx.files_upload(content.encode('utf-8'), dropbox_file_path)
            print(f"Successfully created daily action file '{file_name}' in Dropbox.")
        else:
            raise

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return
    try:
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        daily_action_folder_path = find_daily_action_folder(daily_folder_path)
        create_daily_action_file(daily_action_folder_path, dropbox_vault_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

