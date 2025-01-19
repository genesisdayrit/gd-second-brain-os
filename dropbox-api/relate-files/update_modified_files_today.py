import os
import dropbox
import redis
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import logging
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Redis configuration
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# --- Constants / Keys ---
REDIS_LAST_RUN_KEY = "last_run_folder_journal_relations_at"

# Function to get the Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Initialize Dropbox client using token from Redis
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# -------------------------------------------------------------------
# Redis Timestamp Helpers
# -------------------------------------------------------------------

def get_last_run_time():
    """
    Retrieves the last run timestamp from Redis in UTC.
    If not found, returns None.
    """
    last_run_str = r.get(REDIS_LAST_RUN_KEY)
    if last_run_str is None:
        return None
    
    try:
        # Assuming we stored it as an ISO 8601 string, e.g. "2025-01-18T12:34:56Z"
        return datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
    except ValueError:
        # If parsing fails for some reason, treat as None
        return None


def set_last_run_time(dt_utc):
    """
    Stores the given UTC datetime in Redis as an ISO 8601 string.
    """
    # Convert datetime to a string like "2025-01-18T12:34:56+00:00"
    dt_iso = dt_utc.isoformat()
    r.set(REDIS_LAST_RUN_KEY, dt_iso)

# -------------------------------------------------------------------
# File Path Loader
# -------------------------------------------------------------------

def load_paths(file_path):
    """
    Reads paths from a local text file, one path per line.
    Returns a list of cleaned strings (folder paths).
    """
    try:
        with open(file_path, 'r') as f:
            paths = [line.strip() for line in f.readlines() if line.strip()]
        return paths
    except FileNotFoundError:
        logger.error(f"Error: Paths file '{file_path}' not found.")
        return []

# -------------------------------------------------------------------
# File Filtering Logic
# -------------------------------------------------------------------

def get_modified_files_since_cutoff(paths, cutoff_dt):
    modified_files = []

    for path in paths:
        try:
            logger.info(f"Checking path: {path}")
            response = dbx.files_list_folder(path)

            while True:
                for entry in response.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        client_modified_utc = entry.client_modified

                        # Ensure it's timezone-aware, forcing UTC if naive
                        if client_modified_utc.tzinfo is None:
                            client_modified_utc = client_modified_utc.replace(tzinfo=pytz.utc)

                        if client_modified_utc > cutoff_dt:
                            modified_files.append(entry.path_lower)

                if not response.has_more:
                    break
                response = dbx.files_list_folder_continue(response.cursor)

        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error accessing path {path}: {e}")

    return modified_files

# -------------------------------------------------------------------
# Journal Updater
# -------------------------------------------------------------------

import os
import pytz
import re
import logging
from datetime import datetime

logger = logging.getLogger()

def update_journal_property(file_path):
    """
    Downloads the file, checks if the actual (client_modified) date 
    in the user-defined local timezone is already in the 'Journal:' property,
    and if not, appends it. Then uploads the updated content back to Dropbox.
    """
    try:
        metadata, response = dbx.files_download(file_path)
        content = response.content.decode('utf-8')

        original_file_name = metadata.name
        original_path_display = metadata.path_display

        # 1. Force client_modified to be UTC if naive
        client_modified_utc = metadata.client_modified
        if client_modified_utc.tzinfo is None:
            client_modified_utc = client_modified_utc.replace(tzinfo=pytz.utc)

        # 2. Load the local time zone from environment or default to "America/New_York"
        tz_str = os.getenv("SYSTEM_TIMEZONE", "America/New_York")
        try:
            local_tz = pytz.timezone(tz_str)
        except pytz.UnknownTimeZoneError:
            logger.warning(f"Unknown time zone '{tz_str}', falling back to 'America/New_York'")
            local_tz = pytz.timezone("America/New_York")

        # 3. Convert client_modified (UTC) to local time
        client_modified_local = client_modified_utc.astimezone(local_tz)

        # 4. Format the date for the Journal frontmatter
        #    e.g., "Jan 18, 2025"
        #    If you're on Windows, you might want "%b %d, %Y" instead of "%b %-d, %Y"
        formatted_date = client_modified_local.strftime("%b %-d, %Y")

        # 5. Parse and update frontmatter
        properties_match = re.search(r'---(.*?)---', content, re.DOTALL)
        if properties_match:
            properties_section = properties_match.group(1)

            # Check if the same date is already in the metadata
            if f"[[{formatted_date}]]" in properties_section:
                logger.info(f"Date [[{formatted_date}]] already exists for: {file_path}")
                return  # Skip re-inserting

            # Look for an existing 'Journal:' property
            journal_match = re.search(r'Journal:\s*(.*?)(?=\n\S|$)', properties_section, re.DOTALL)
            if journal_match:
                journal_entries = journal_match.group(1).splitlines()

                # Detect indentation from the first line
                if journal_entries:
                    indentation = " " * (len(journal_entries[0]) - len(journal_entries[0].lstrip()))
                else:
                    indentation = "    "

                # Append the new date
                formatted_date_entry = f"{indentation}- \"[[{formatted_date}]]\""
                journal_entries.append(formatted_date_entry)

                updated_journal = "Journal:\n" + "\n".join(journal_entries)
                updated_properties = re.sub(
                    r'Journal:\s*(.*?)(?=\n\S|$)',
                    updated_journal,
                    properties_section,
                    flags=re.DOTALL
                )
            else:
                # No 'Journal:' property yet; add it
                updated_properties = properties_section + f"\nJournal:\n    - \"[[{formatted_date}]]\""

            # Rebuild the file content, ensuring the closing '---' is on a new line
            body_after_frontmatter = content.split('---', 2)[2].strip()
            updated_content = f"---\n{updated_properties.strip()}\n---\n{body_after_frontmatter}"

        else:
            # No existing frontmatter, create a new section
            updated_content = (
                f"---\nJournal:\n    - \"[[{formatted_date}]]\"\n---\n{content}"
            )

        # 6. Overwrite the file in Dropbox
        dbx.files_upload(
            updated_content.encode('utf-8'),
            original_path_display,
            mode=dropbox.files.WriteMode.overwrite
        )
        logger.info(f"Updated Journal property for file: {original_file_name}")

    except Exception as e:
        logger.error(f"Error updating file {file_path}: {e}")

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main():
    logger.info("Starting script to check modified files and update Journal property.")

    # 1. Load folder paths from text file
    paths_file = "paths_to_check.txt"  # File containing the list of folder paths
    paths_to_check = load_paths(paths_file)

    if not paths_to_check:
        logger.error("No paths to check. Please ensure 'paths_to_check.txt' is populated.")
        return

    # 2. Determine cutoff for picking files
    now_utc = datetime.now(pytz.utc)
    cutoff_23h55 = now_utc - timedelta(hours=23, minutes=55)

    # Read last run time from Redis (if any)
    last_run_dt = get_last_run_time()

    if last_run_dt is None:
        # If never run before, fall back to 24 hours ago
        fallback_24h_ago = now_utc - timedelta(hours=24)
        logger.info("No previous run timestamp found in Redis; defaulting to 24h ago.")
        last_run_dt = fallback_24h_ago

    # Final cutoff is the max of '23h55 ago' vs 'last_run_dt'
    final_cutoff = max(cutoff_23h55, last_run_dt)
    logger.info(f"Using cutoff UTC datetime: {final_cutoff.isoformat()}")

    # 3. Fetch all modified files since final_cutoff
    modified_files = get_modified_files_since_cutoff(paths_to_check, final_cutoff)

    if modified_files:
        logger.info("Files modified in our cutoff window:")
        for file_path in modified_files:
            logger.info(f"Processing file: {file_path}")
            update_journal_property(file_path)
    else:
        logger.info("No files were modified in the cutoff window.")

    # 4. Update the last run timestamp in Redis to now
    set_last_run_time(now_utc)
    logger.info("Script completed successfully. Updated last run time in Redis.")

# -------------------------------------------------------------------
# Entry Point
# -------------------------------------------------------------------

if __name__ == "__main__":
    main()

