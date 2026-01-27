import os
import redis
import dropbox
import yaml 
import logging
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import argparse

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Load Environment Variables ---
load_dotenv()

# --- Timezone Configuration ---
timezone_str = os.getenv("SYSTEM_TIMEZONE", "US/Eastern")
logger.info(f"Using timezone: {timezone_str}")

# --- Redis Configuration ---
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# --- Get Dropbox Access Token from Redis ---
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        logger.error("Dropbox access token not found in Redis.")
        raise EnvironmentError("Dropbox access token not found in Redis.")
    logger.info("Dropbox access token retrieved from Redis.")
    return access_token

# --- Initialize Dropbox Client ---
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
logger.info("Dropbox client initialized.")

# --- Date Functions Using Tomorrow's Date ---
def get_tomorrow():
    """Return tomorrow's datetime object in the configured timezone."""
    return datetime.now(pytz.timezone(timezone_str)) + timedelta(days=1)

def get_day_of_week():
    tomorrow = get_tomorrow()
    return tomorrow.strftime('%A')

def get_week_ending_sunday():
    tomorrow = get_tomorrow()
    # Sunday is 6 (Monday = 0)
    days_until_sunday = (6 - tomorrow.weekday()) % 7
    week_ending = tomorrow + timedelta(days=days_until_sunday)
    return week_ending.strftime('%Y-%m-%d')

def get_week_ending_filenames():
    week_ending = get_week_ending_sunday()
    return {
        "week_ending": f"Week-Ending-{week_ending}",
        "weekly_map": f"Weekly Map {week_ending}"
    }

def get_cycle_date_range():
    tomorrow = get_tomorrow()
    # Wednesday = 2; compute days since last Wednesday based on tomorrow
    days_since_wednesday = (tomorrow.weekday() - 2) % 7
    cycle_start = tomorrow - timedelta(days=days_since_wednesday)
    cycle_end = cycle_start + timedelta(days=6)
    return f"{cycle_start.strftime('%b. %d')} - {cycle_end.strftime('%b. %d, %Y')}"

def get_weekly_newsletter_filename():
    week_end_date_str = get_week_ending_sunday()  # "YYYY-MM-DD"
    week_end_date = datetime.strptime(week_end_date_str, '%Y-%m-%d')
    return week_end_date.strftime("Weekly Newsletter %b. %d, %Y")

def get_tomorrow_date():
    return get_tomorrow().strftime('%Y-%m-%d')

def get_tomorrow_iso_date():
    return get_tomorrow_date()

def get_tomorrow_filename():
    """
    Format tomorrow's date to match the journal filename format.
    Note: For Linux/macOS use '%-d', for Windows '%#d'
    """
    tomorrow = get_tomorrow()
    try:
        return tomorrow.strftime('%b %-d, %Y.md')
    except Exception:
        return tomorrow.strftime('%b %#d, %Y.md')

def get_one_year_ago_date():
    """
    Calculate one year ago from tomorrow's date with proper leap year handling.
    For Feb 29 on leap years, falls back to Feb 28 on non-leap years.
    """
    tomorrow = get_tomorrow()
    try:
        # Try to get the same date one year ago
        one_year_ago = tomorrow.replace(year=tomorrow.year - 1)
        return one_year_ago
    except ValueError:
        # This happens when tomorrow is Feb 29 and last year wasn't a leap year
        # Fall back to Feb 28
        if tomorrow.month == 2 and tomorrow.day == 29:
            one_year_ago = tomorrow.replace(year=tomorrow.year - 1, day=28)
            logger.info(f"Leap year adjustment: Feb 29 -> Feb 28 for year {tomorrow.year - 1}")
            return one_year_ago
        else:
            # Re-raise if it's a different kind of error
            raise

def get_one_year_ago_filename():
    """
    Format one year ago date to match the journal filename format for the 'On this Day' property.
    Note: For Linux/macOS use '%-d', for Windows '%#d'
    """
    one_year_ago = get_one_year_ago_date()
    try:
        filename = one_year_ago.strftime('%b %-d, %Y')
    except Exception:
        filename = one_year_ago.strftime('%b %#d, %Y')
    
    logger.info(f"One year ago filename: {filename}")
    return filename

# --- Dropbox File/Folder Helper Functions ---
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

def get_long_cycle_filename():
    """
    Scan the _6-Week-Cycles folder and find which file contains tomorrow's date.
    Returns the filename string that matches tomorrow's date range.
    """
    tomorrow = get_tomorrow().date()
    
    vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
    if not vault_path:
        logger.error("DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set.")
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

def process_mapping(mapping, vault_path):
    """
    Processes a mapping object:
      1. Finds the parent folder in the vault.
      2. Searches within that parent for the target subfolder.
      3. Looks up the file in the target folder using a contains search.
    Returns a dict with key, file_path, file_name, and the constructed relationship link.
    """
    file_string = mapping["target_file_string"]
    logger.info(f"Processing mapping for key '{mapping['key']}' using file search string: {file_string}")

    parent_folder = find_folder_in_path(vault_path, mapping["parent_folder"])
    if not parent_folder:
        logger.error(f"Parent folder containing '{mapping['parent_folder']}' not found in vault '{vault_path}'.")
        return None

    target_folder = find_folder_in_path(parent_folder, mapping["target_folder"])
    if not target_folder:
        logger.error(f"Target folder containing '{mapping['target_folder']}' not found within parent folder '{mapping['parent_folder']}'.")
        return None

    file_path, file_name = lookup_file_in_folder(target_folder, file_string)
    if not file_path:
        logger.error(f"File for mapping key '{mapping['key']}' not found in target folder.")
        return None

    # Remove .md extension if present before constructing the relationship link.
    base_name = file_name
    if base_name.lower().endswith('.md'):
        base_name = base_name[:-3]

    return {
        "key": mapping["key"],
        "file_path": file_path,
        "file_name": file_name,
        "relationship": f"[[{base_name}]]"  # Relationship without the .md extension.
    }

def get_dynamic_mappings():
    """
    Generates a dictionary of dynamic mappings using date transformations and Dropbox file lookups.
    The returned dictionary maps property keys to their relationship strings.
    """
    week_ending = get_week_ending_sunday()
    filenames = get_week_ending_filenames()
    cycle_date_range = get_cycle_date_range()
    weekly_newsletter = get_weekly_newsletter_filename()
    long_cycle_filename = get_long_cycle_filename()

    # Define mappings with an added "key" property to designate YAML keys.
    mappings = [
        {
            "key": "Weeks",
            "parent_folder": "_Weekly",
            "target_folder": "_Weeks",
            "target_file_string": week_ending
        },
        {
            "key": "Weekly Map",
            "parent_folder": "_Weekly",
            "target_folder": "_Weekly-Maps",
            "target_file_string": filenames["weekly_map"]
        },
        {
            "key": "_Cycles",
            "parent_folder": "_Cycles",
            "target_folder": "_Weekly-Cycles",
            "target_file_string": cycle_date_range
        },
        {
            "key": "_Weekly Health Reviews",
            "parent_folder": "_Weekly",
            "target_folder": "_Weekly-Health-Review",
            "target_file_string": cycle_date_range
        },
        {
            "key": "Newsletter",
            "parent_folder": "_Weekly",
            "target_folder": "_Newsletters",
            "target_file_string": weekly_newsletter
        }
    ]

    # Only add the _Long-Cycle mapping if we found a matching file
    if long_cycle_filename:
        mappings.append({
            "key": "_Long-Cycle",
            "parent_folder": "_Cycles",
            "target_folder": "_6-Week-Cycles",
            "target_file_string": long_cycle_filename
        })

    vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
    if not vault_path:
        logger.error("DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set.")
        raise EnvironmentError("DROPBOX_OBSIDIAN_VAULT_PATH is not set.")

    dynamic_mappings = {}
    for mapping in mappings:
        result = process_mapping(mapping, vault_path)
        if result:
            dynamic_mappings[result["key"]] = result["relationship"]
    return dynamic_mappings

# --- Journal Folder Lookup ---
def get_journal_folder_path(vault_path):
    """
    Finds the _Daily folder in the vault and then locates the _Journal folder within it.
    """
    daily_folder = find_folder_in_path(vault_path, "_Daily")
    if not daily_folder:
        raise FileNotFoundError("Could not find the _Daily folder in the vault.")
    journal_folder = find_folder_in_path(daily_folder, "_Journal")
    if not journal_folder:
        raise FileNotFoundError("Could not find the _Journal folder within the _Daily folder.")
    return journal_folder

# --- Journal YAML Update Functions ---
def get_tomorrow_filename_for_journal():
    """
    Returns the filename for tomorrow's journal entry.
    """
    tomorrow_filename = get_tomorrow_filename()
    logger.info(f"Looking for tomorrow's journal file: {tomorrow_filename}")
    return tomorrow_filename

def find_tomorrow_journal_entry(journal_folder):
    """
    Locates tomorrow's journal entry inside the given journal_folder.
    Returns a tuple of (file_path, original_file_name).
    """
    tomorrow_filename = get_tomorrow_filename_for_journal()
    logger.info(f"Looking for tomorrow's journal file: {tomorrow_filename}")
    all_files = []
    try:
        response = dbx.files_list_folder(journal_folder)
        all_files.extend(response.entries)
        while response.has_more:
            response = dbx.files_list_folder_continue(response.cursor)
            all_files.extend(response.entries)
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Error fetching journal files from {journal_folder}: {e}")
        raise

    for entry in all_files:
        if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower() == tomorrow_filename.lower():
            logger.info(f"Found tomorrow's journal file: {entry.name}")
            return entry.path_lower, entry.name  # Preserve original filename casing.
    raise FileNotFoundError(f"No journal file found for tomorrow's date ({tomorrow_filename}) in '{journal_folder}'")

def retrieve_file_content(file_path):
    """Retrieve the content of a file from Dropbox."""
    try:
        _, response = dbx.files_download(file_path)
        return response.content.decode('utf-8')
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Error downloading file from {file_path}: {e}")
        return None

def extract_yaml_metadata(file_content):
    """
    Extract YAML front matter from the file content.
    Returns a tuple (metadata, remaining_content).
    """
    lines = file_content.splitlines()
    if lines and lines[0].strip() == "---":
        yaml_lines = []
        content_start = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                content_start = i + 1
                break
            yaml_lines.append(line)
        yaml_str = "\n".join(yaml_lines)
        try:
            metadata = yaml.safe_load(yaml_str) or {}
            remaining_content = "\n".join(lines[content_start:]) if content_start is not None else ""
            return metadata, remaining_content
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML: {e}")
            return None, None
    return {}, file_content

def update_yaml_metadata(metadata, dynamic_mappings):
    """
    Update YAML metadata with tomorrow's day of week, date, dynamic relationship mappings,
    add the Daily Action property as a list relationship, and add the 'On this Day' property
    with the one year ago journal reference.
    For keys that should be lists (e.g., 'Weeks', '_Weekly Health Reviews', '_Cycles', 'Daily Action', 'On this Day'),
    the value is assigned as a list.
    """
    # Update simple fields using tomorrow's date
    metadata["Day of Week"] = get_day_of_week()
    metadata["Date"] = get_tomorrow_iso_date()

    # Define which keys should be list properties
    list_keys = {"Weeks", "_Weekly Health Reviews", "_Cycles", "_Long-Cycle", "Daily Action", "On this Day"}

    for key, relationship in dynamic_mappings.items():
        if key in list_keys:
            metadata[key] = [relationship]
        else:
            metadata[key] = relationship

    # Add the Daily Action property as a list relationship formatted as '[[DA YYYY-MM-DD]]'
    daily_action = f"[[DA {get_tomorrow_date()}]]"
    metadata["Daily Action"] = [daily_action]

    # Add the 'On this Day' property with one year ago journal reference
    one_year_ago_filename = get_one_year_ago_filename()
    metadata["On this Day"] = [f"[[{one_year_ago_filename}]]"]

    return metadata

def save_updated_file(file_path, file_name, updated_metadata, content):
    """
    Convert updated metadata back to YAML front matter, merge with the original content,
    and upload the file to Dropbox (overwriting the existing file).
    """
    yaml_str = yaml.safe_dump(updated_metadata, default_flow_style=False, sort_keys=False)
    new_file_content = f"---\n{yaml_str}---\n{content}"
    upload_path = os.path.join(os.path.dirname(file_path), file_name)
    try:
        dbx.files_upload(
            new_file_content.encode('utf-8'),
            upload_path,
            mode=dropbox.files.WriteMode.overwrite
        )
        logger.info(f"Updated file uploaded successfully: {upload_path}")
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Error uploading updated file to {upload_path}: {e}")

# --- Main Workflow ---
def main():
    try:
        # Step 1: Check if tomorrow's journal exists first (early exit if not found)
        vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
        if not vault_path:
            logger.error("DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set.")
            return
        
        logger.info("Checking if tomorrow's journal exists before proceeding...")
        journal_folder_path = get_journal_folder_path(vault_path)
        journal_file_path, journal_file_name = find_tomorrow_journal_entry(journal_folder_path)
        logger.info(f"Tomorrow's journal entry found at: {journal_file_path}")

        # Step 2: Retrieve file content and extract YAML front matter (early validation)
        file_content = retrieve_file_content(journal_file_path)
        if not file_content:
            logger.error("Unable to retrieve journal file content.")
            return
        metadata, remaining_content = extract_yaml_metadata(file_content)
        if metadata is None:
            logger.error("No valid YAML metadata found in journal file.")
            return

        # Step 3: Now that we know the journal exists, generate dynamic mappings (expensive operations)
        logger.info("Journal found - proceeding with dynamic mappings lookup...")
        dynamic_mappings = get_dynamic_mappings()
        logger.info(f"Dynamic mappings: {dynamic_mappings}")

        # Step 4: Update YAML metadata with tomorrow's date info, dynamic mappings, and Daily Action.
        updated_metadata = update_yaml_metadata(metadata, dynamic_mappings)

        # Step 5: Save the updated journal file back to Dropbox.
        save_updated_file(journal_file_path, journal_file_name, updated_metadata, remaining_content)

    except FileNotFoundError as e:
        logger.warning(f"Tomorrow's journal not found - skipping update: {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()

