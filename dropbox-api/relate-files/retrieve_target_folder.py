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

# Function to find a folder by name suffix in the Dropbox vault path with pagination
def find_folder_by_suffix(vault_path, suffix):
    try:
        folders_found = []
        response = dbx.files_list_folder(vault_path)

        # Retrieve all entries with pagination
        while True:
            for entry in response.entries:
                if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith(suffix):
                    print(f"Found folder: {entry.name}")
                    return entry.path_lower

            if not response.has_more:
                break
            response = dbx.files_list_folder_continue(response.cursor)

        raise FileNotFoundError(f"No folder found with suffix '{suffix}' in '{vault_path}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching folder list: {e}")
        raise

# Function to list files in a target folder sorted by most recent modification
def list_sorted_files(target_folder):
    try:
        files_metadata = []
        response = dbx.files_list_folder(target_folder)

        # Retrieve all files with pagination
        while True:
            files_metadata.extend(response.entries)
            if not response.has_more:
                break
            response = dbx.files_list_folder_continue(response.cursor)

        # Filter only files and sort by modification time
        sorted_files = sorted(
            [file for file in files_metadata if isinstance(file, dropbox.files.FileMetadata)],
            key=lambda x: x.server_modified,
            reverse=True
        )

        for file in sorted_files:
            print(f"File Name: {file.name}, Modified: {file.server_modified}, Path: {file.path_lower}")

    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching files from folder: {e}")
        raise

# Main function
def main():
    try:
        # Base Dropbox path for the Obsidian vault
        dropbox_vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
        if not dropbox_vault_path:
            raise EnvironmentError("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set")

        # Find the target folder by suffix
        target_folder_suffix = "_Experiences+Events+Meetings+Sessions"
        target_folder = find_folder_by_suffix(dropbox_vault_path, target_folder_suffix)

        print(f"Listing contents of folder: {target_folder}")
        list_sorted_files(target_folder)

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except EnvironmentError as e:
        print(f"Environment Error: {e}")

if __name__ == "__main__":
    main()
