import os
import dropbox
import redis
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

def get_dropbox_access_token():
    """Retrieve the Dropbox access token from Redis."""
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

def find_daily_folder(vault_path):
    """Search for the '_Daily' folder in the specified vault path."""
    result = dbx.files_list_folder(vault_path)
    for entry in result.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily' in Dropbox")

def find_journal_folder(daily_folder_path):
    """Search for the '_Journal' folder inside the '_Daily' folder."""
    result = dbx.files_list_folder(daily_folder_path)
    for entry in result.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Journal"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Journal' in Dropbox")

def list_all_files_in_folder(folder_path):
    """List all files in the specified folder, including pagination."""
    all_files = []
    result = dbx.files_list_folder(folder_path)

    while True:
        all_files.extend(result.entries)
        if not result.has_more:
            break
        result = dbx.files_list_folder_continue(result.cursor)

    return all_files

def main():
    try:
        # Retrieve Dropbox access token from Redis
        dropbox_access_token = get_dropbox_access_token()

        # Initialize Dropbox client
        global dbx
        dbx = dropbox.Dropbox(dropbox_access_token)

        # Get the Dropbox vault path from the environment variable
        vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
        if not vault_path:
            raise EnvironmentError("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set.")

        # Locate the _Daily folder
        daily_folder_path = find_daily_folder(vault_path)
        print(f"Found _Daily folder at: {daily_folder_path}")

        # Locate the _Journal folder inside _Daily
        journal_folder_path = find_journal_folder(daily_folder_path)
        print(f"Found _Journal folder at: {journal_folder_path}")

        # List all files in the _Journal folder
        all_files = list_all_files_in_folder(journal_folder_path)
        print("Files in _Journal folder:")
        for entry in all_files:
            if isinstance(entry, dropbox.files.FileMetadata):
                print(f"File Name: {entry.name}, Modified: {entry.client_modified}, Path: {entry.path_lower}")
            elif isinstance(entry, dropbox.files.FolderMetadata):
                print(f"Folder Name: {entry.name}, Path: {entry.path_lower}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except EnvironmentError as e:
        print(f"Environment Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

