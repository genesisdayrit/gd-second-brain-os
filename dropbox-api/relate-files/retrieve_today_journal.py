import os
import dropbox
import redis
from datetime import datetime
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

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

# Function to find the '_Daily' folder
def find_daily_folder(vault_path):
    try:
        response = dbx.files_list_folder(vault_path)

        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and '_daily' in entry.name.lower():
                print(f"Found Daily folder: {entry.name}")
                return entry.path_lower

        raise FileNotFoundError(f"No folder found with '_Daily' in '{vault_path}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching folder list: {e}")
        raise

# Function to find the '_Journal' subfolder
def find_journal_folder(daily_folder_path):
    try:
        response = dbx.files_list_folder(daily_folder_path)

        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and '_journal' in entry.name.lower():
                print(f"Found Journal folder: {entry.name}")
                return entry.path_lower

        raise FileNotFoundError(f"No folder found with '_Journal' in '{daily_folder_path}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching folder list: {e}")
        raise

# Function to find today's journal entry with pagination handling
def find_today_journal_entry(journal_folder):
    try:
        # Format today's date as 'Month DD, YYYY.md'
        today = datetime.now(pytz.timezone('US/Eastern')).strftime('%b %d, %Y.md').lower()
        all_files = []
        response = dbx.files_list_folder(journal_folder)

        # Retrieve all files, handling pagination
        while True:
            all_files.extend(response.entries)
            if not response.has_more:
                break
            response = dbx.files_list_folder_continue(response.cursor)

        # Search for today's journal file
        for entry in all_files:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower() == today:
                print(f"Found today's journal file: {entry.name}")
                return entry.path_lower

        raise FileNotFoundError(f"No journal file found for today's date ({today}) in '{journal_folder}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching journal files: {e}")
        raise

# Main function
def main():
    # Base Dropbox path for the Obsidian vault
    dropbox_vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set")
        return

    try:
        # Locate the _Daily folder
        daily_folder_path = find_daily_folder(dropbox_vault_path)

        # Locate the _Journal folder inside _Daily
        journal_folder_path = find_journal_folder(daily_folder_path)

        # Find today's journal entry
        today_journal_entry = find_today_journal_entry(journal_folder_path)

        print(f"Today's journal entry is located at: {today_journal_entry}")
    except FileNotFoundError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
