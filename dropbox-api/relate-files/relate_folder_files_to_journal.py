import os
import dropbox
import redis
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

# Load environment variables from .env file
load_dotenv()

# --- Timezone Configuration ---
timezone_str = os.getenv("SYSTEM_TIMEZONE", "US/Eastern")
logger.info(f"Using timezone: {timezone_str}")

# Redis configuration
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Function to get the Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Initialize Dropbox client using token from Redis
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# Lookback period in days
LOOKBACK_DAYS = 1

def find_daily_folder(vault_path):
    """Search for a folder in the Dropbox vault path containing '_Daily'."""
    try:
        response = dbx.files_list_folder(vault_path)

        # Look for a folder that contains '_Daily'
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and '_Daily' in entry.name:
                print(f"Found Daily folder: {entry.name}")
                return entry.path_lower

        raise FileNotFoundError(f"No folder found with '_Daily' in '{vault_path}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching folder list: {e}")
        raise

def find_journal_folder(daily_folder_path):
    """Search for a '_Journal' subfolder inside the '_Daily' folder."""
    try:
        response = dbx.files_list_folder(daily_folder_path)

        # Look for a subfolder named '_Journal'
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and '_Journal' in entry.name:
                print(f"Found Journal folder: {entry.name}")
                return entry.path_lower

        raise FileNotFoundError(f"No folder found with '_Journal' in '{daily_folder_path}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching folder list: {e}")
        raise

def find_experiences_folder(vault_path):
    """Search for a folder in the Dropbox vault path containing '_Experiences+Events+Meetings+Sessions'."""
    try:
        response = dbx.files_list_folder(vault_path)

        # Look for a folder that contains '_Experiences+Events+Meetings+Sessions'
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and '_Experiences+Events+Meetings+Sessions' in entry.name:
                print(f"Found folder: {entry.name}")
                return entry.path_lower

        raise FileNotFoundError(f"No folder found with '_Experiences+Events+Meetings+Sessions' in '{vault_path}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching folder list: {e}")
        raise

def fetch_sorted_files_metadata(folder_path):
    """Fetch all files metadata from Dropbox and sort them by creation time (client_modified)."""
    files_metadata = []
    try:
        # Initial request to list folder
        response = dbx.files_list_folder(folder_path)
        files_metadata.extend(response.entries)

        # Continue fetching if there are more files
        while response.has_more:
            response = dbx.files_list_folder_continue(response.cursor)
            files_metadata.extend(response.entries)

        # Sort files by creation time (client_modified) in descending order
        files_metadata.sort(key=lambda x: x.client_modified, reverse=True)

    except dropbox.exceptions.ApiError as err:
        print(f"Failed to fetch metadata from Dropbox: {err}")
        return []

    return files_metadata

def filter_recent_files(files_metadata, lookback_days):
    """Filter files that were created or modified in the last 'lookback_days' days using system timezone."""
    recent_files = []
    lookback_date = datetime.now(pytz.timezone(timezone_str)) - timedelta(days=lookback_days)

    for entry in files_metadata:
        if isinstance(entry, dropbox.files.FileMetadata):
            # Use client_modified for created date
            created_time = entry.client_modified.astimezone(pytz.timezone(timezone_str))

            if created_time >= lookback_date:
                recent_files.append({
                    'name': entry.name,
                    'created': created_time,
                    'last_modified': entry.server_modified,
                    'path_lower': entry.path_lower
                })

    return recent_files

def find_journal_file_by_date(journal_folder, formatted_date):
    """Search for the journal file in the '_Journal' folder that matches the formatted date."""
    try:
        # Append .md to the formatted date to match the journal file name
        formatted_filename = f"{formatted_date}.md"
        
        # Fetch sorted files from the journal folder
        files_metadata = fetch_sorted_files_metadata(journal_folder)

        for entry in files_metadata:
            print(f"Checking journal file: {entry.name} against {formatted_filename}")
            if isinstance(entry, dropbox.files.FileMetadata) and formatted_filename == entry.name:
                print(f"Found Journal file: {entry.name}")
                return entry.path_lower

        raise FileNotFoundError(f"No journal file found for date '{formatted_filename}' in '{journal_folder}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching journal files: {e}")
        raise

def update_journal_file(journal_file_path, experiences_list):
    """Update the journal file by appending event links to the '_Experiences / Events / Meetings / Sessions:' property."""
    try:
        # Download the file content from Dropbox
        _, file_content = dbx.files_download(journal_file_path)
        file_text = file_content.content.decode('utf-8')

        # Find the YAML property and append the new experiences
        if '_Experiences / Events / Meetings / Sessions:' in file_text:
            lines = file_text.splitlines()
            updated_content = ""
            experiences_added = False

            for line in lines:
                updated_content += line + "\n"
                # Add experiences with quotes around the double-bracketed link
                if '_Experiences / Events / Meetings / Sessions:' in line and not experiences_added:
                    for experience in experiences_list:
                        experience_name = os.path.splitext(experience)[0]  # Get the file name without the extension
                        updated_content += f'  - "[[{experience_name}]]"\n'  # Add quotes around the link
                    experiences_added = True

            # Upload the updated content back to Dropbox
            dbx.files_upload(updated_content.encode('utf-8'), journal_file_path, mode=dropbox.files.WriteMode.overwrite)
            print(f"Updated journal file: {journal_file_path}")
        else:
            print(f"YAML property '_Experiences / Events / Meetings / Sessions:' not found in file: {journal_file_path}")
    except dropbox.exceptions.ApiError as e:
        print(f"Error updating journal file: {e}")
        raise

    except dropbox.exceptions.ApiError as e:
        print(f"Error updating journal file: {e}")
        raise

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return

    try:
        # Find the '_Daily' folder in Dropbox
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        
        # Find the '_Journal' subfolder inside the '_Daily' folder
        journal_folder_path = find_journal_folder(daily_folder_path)

        # Fetch sorted files metadata from the Experiences folder
        print(f"Fetching all files from the '_Experiences+Events+Meetings+Sessions' folder...")
        experiences_folder_path = find_experiences_folder(dropbox_vault_path)
        all_files_metadata = fetch_sorted_files_metadata(experiences_folder_path)

        # Filter files created in the last LOOKBACK_DAYS
        recent_files = filter_recent_files(all_files_metadata, LOOKBACK_DAYS)
        
        if recent_files:
            print(f"Files modified or created in the last {LOOKBACK_DAYS} day(s):")
            for file in recent_files:
                print(f"File: {file['name']}, Created: {file['created']}, Last Modified: {file['last_modified']}")

                # Format the created date to match the journal file name (e.g., Oct 13, 2024.md)
                formatted_date = file['created'].strftime('%b %d, %Y')

                # Find the corresponding journal file
                journal_file_path = find_journal_file_by_date(journal_folder_path, formatted_date)

                # Update the journal file with event links
                update_journal_file(journal_file_path, [file['name']])
        else:
            print(f"No files modified or created in the last {LOOKBACK_DAYS} day(s).")
    except FileNotFoundError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()


