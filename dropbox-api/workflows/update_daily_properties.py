import os
import redis
import dropbox
import yaml  # Install with: pip install pyyaml
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

# --- Date Functions ---
def get_day_of_week():
    today = datetime.now(pytz.timezone(timezone_str))
    return today.strftime('%A')

def get_week_ending_sunday():
    today = datetime.now(pytz.timezone(timezone_str))
    # Sunday is 6 (Monday = 0)
    days_until_sunday = (6 - today.weekday()) % 7
    week_ending = today + timedelta(days=days_until_sunday)
    return week_ending.strftime('%Y-%m-%d')

def get_week_ending_filenames():
    week_ending = get_week_ending_sunday()
    return {
        "week_ending": f"Week-Ending-{week_ending}",
        "weekly_map": f"Weekly Map {week_ending}"
    }

def get_cycle_date_range():
    today = datetime.now(pytz.timezone(timezone_str))
    # Wednesday = 2; compute days since last Wednesday
    days_since_wednesday = (today.weekday() - 2) % 7
    cycle_start = today - timedelta(days=days_since_wednesday)
    cycle_end = cycle_start + timedelta(days=6)
    return f"{cycle_start.strftime('%b. %d')} - {cycle_end.strftime('%b. %d, %Y')}"

def get_weekly_newsletter_filename():
    week_end_date_str = get_week_ending_sunday()  # "YYYY-MM-DD"
    week_end_date = datetime.strptime(week_end_date_str, '%Y-%m-%d')
    return week_end_date.strftime("Weekly Newsletter %b. %d, %Y")

def get_today_date():
    today = datetime.now(pytz.timezone(timezone_str))
    return today.strftime('%Y-%m-%d')

def get_today_iso_date():
    return get_today_date()

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
def get_today_filename():
    """
    Format today's date to match the journal filename format.
    Note: For Linux/macOS use '%-d', for Windows '%#d'
    """
    today = datetime.now(pytz.timezone(timezone_str))
    try:
        return today.strftime('%b %-d, %Y.md')
    except Exception:
        return today.strftime('%b %#d, %Y.md')

def find_today_journal_entry(journal_folder):
    """
    Locates today's journal entry inside the given journal_folder.
    Returns a tuple of (file_path, original_file_name).
    """
    today_filename = get_today_filename()
    logger.info(f"Looking for today's journal file: {today_filename}")
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
        if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower() == today_filename.lower():
            logger.info(f"Found today's journal file: {entry.name}")
            return entry.path_lower, entry.name  # Preserve original filename casing.
    raise FileNotFoundError(f"No journal file found for today's date ({today_filename}) in '{journal_folder}'")

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
    Update YAML metadata with the current day of week, date, dynamic relationship mappings,
    and add the Daily Action property as a list relationship.
    For keys that should be lists (e.g., 'Weeks', '_Weekly Health Reviews', '_Cycles', 'Daily Action'),
    the value is assigned as a list.
    """
    # Update simple fields
    metadata["Day of Week"] = get_day_of_week()
    metadata["Date"] = get_today_iso_date()

    # Define which keys should be list properties
    list_keys = {"Weeks", "_Weekly Health Reviews", "_Cycles", "Daily Action"}

    for key, relationship in dynamic_mappings.items():
        if key in list_keys:
            metadata[key] = [relationship]
        else:
            metadata[key] = relationship

    # Add the Daily Action property as a list relationship formatted as '[[DA YYYY-MM-DD]]'
    daily_action = f"[[DA {get_today_date()}]]"
    metadata["Daily Action"] = [daily_action]

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
        # Step 1: Generate dynamic mappings based on date and file lookups.
        dynamic_mappings = get_dynamic_mappings()
        logger.info(f"Dynamic mappings: {dynamic_mappings}")

        # Step 2: Locate today's journal note using a dynamic lookup of _Daily then _Journal.
        vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
        if not vault_path:
            logger.error("DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set.")
            return
        journal_folder_path = get_journal_folder_path(vault_path)
        journal_file_path, journal_file_name = find_today_journal_entry(journal_folder_path)
        logger.info(f"Today's journal entry located at: {journal_file_path}")

        # Step 3: Retrieve file content and extract YAML front matter.
        file_content = retrieve_file_content(journal_file_path)
        if not file_content:
            logger.error("Unable to retrieve journal file content.")
            return
        metadata, remaining_content = extract_yaml_metadata(file_content)
        if metadata is None:
            logger.error("No valid YAML metadata found in journal file.")
            return

        # Step 4: Update YAML metadata with current date info, dynamic mappings, and Daily Action.
        updated_metadata = update_yaml_metadata(metadata, dynamic_mappings)

        # Step 5: Save the updated journal file back to Dropbox.
        save_updated_file(journal_file_path, journal_file_name, updated_metadata, remaining_content)

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()

