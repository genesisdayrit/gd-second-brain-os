import os
import dropbox
import redis
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
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

# Lookback period in days
LOOKBACK_DAYS = 1

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

def fetch_all_files_metadata(folder_path):
    """Fetch all files metadata from Dropbox, handling pagination."""
    files_metadata = []
    try:
        # Initial request to list folder
        response = dbx.files_list_folder(folder_path)
        files_metadata.extend(response.entries)

        # Continue fetching if there are more files
        while response.has_more:
            response = dbx.files_list_folder_continue(response.cursor)
            files_metadata.extend(response.entries)

    except dropbox.exceptions.ApiError as err:
        print(f"Failed to fetch metadata from Dropbox: {err}")
        return []

    return files_metadata

def filter_recent_files(files_metadata, lookback_days):
    """Filter files that were created or modified in the last 'lookback_days' days."""
    recent_files = []
    lookback_date = datetime.now() - timedelta(days=lookback_days)

    for entry in files_metadata:
        if isinstance(entry, dropbox.files.FileMetadata):
            # Filter by client_modified or server_modified (whichever is later)
            modified_time = entry.server_modified

            if modified_time >= lookback_date:
                recent_files.append({
                    'name': entry.name,
                    'created': entry.client_modified,
                    'last_modified': entry.server_modified,
                    'path_lower': entry.path_lower
                })

    return recent_files

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return

    try:
        # Find the '_Experiences+Events+Meetings+Sessions' folder in Dropbox
        experiences_folder_path = find_experiences_folder(dropbox_vault_path)

        # Fetch all files metadata from the found folder
        print(f"Fetching all files from '{experiences_folder_path}'...")
        all_files_metadata = fetch_all_files_metadata(experiences_folder_path)
        
        # Filter files created or modified in the last LOOKBACK_DAYS
        recent_files = filter_recent_files(all_files_metadata, LOOKBACK_DAYS)
        
        if recent_files:
            print(f"Files modified or created in the last {LOOKBACK_DAYS} day(s):")
            for file in recent_files:
                print(f"File: {file['name']}, Created: {file['created']}, Last Modified: {file['last_modified']}")
        else:
            print(f"No files modified or created in the last {LOOKBACK_DAYS} day(s).")
    except FileNotFoundError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

