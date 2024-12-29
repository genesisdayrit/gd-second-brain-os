import os
import dropbox
import redis
from dotenv import load_dotenv
import json

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

# Function to find the '_Journal' folder and retrieve metadata for the latest file
def find_journal_and_retrieve_metadata(vault_path):
    try:
        # Search for the '_Journal' folder
        response = dbx.files_list_folder(vault_path)

        journal_folder = None
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and '_Journal' in entry.name:
                journal_folder = entry.path_lower
                print(f"Found '_Journal' folder: {journal_folder}")
                break

        if not journal_folder:
            raise FileNotFoundError("No folder with '_Journal' found in the specified vault path.")

        # List files in the '_Journal' folder
        response = dbx.files_list_folder(journal_folder)
        files = [entry for entry in response.entries if isinstance(entry, dropbox.files.FileMetadata)]

        while response.has_more:
            response = dbx.files_list_folder_continue(response.cursor)
            files.extend(entry for entry in response.entries if isinstance(entry, dropbox.files.FileMetadata))

        if not files:
            print("No files found in the '_Journal' folder.")
            return

        # Find the latest file by server_modified date
        latest_file = max(files, key=lambda x: x.server_modified)

        # Extract metadata and print as JSON
        metadata = {
            "name": latest_file.name,
            "path_lower": latest_file.path_lower,
            "id": latest_file.id,
            "client_modified": latest_file.client_modified.isoformat(),
            "server_modified": latest_file.server_modified.isoformat(),
            "size": latest_file.size,
            "is_downloadable": latest_file.is_downloadable,
        }
        print("Raw metadata for the latest file:")
        print(json.dumps(metadata, indent=4))

    except dropbox.exceptions.ApiError as e:
        print(f"Error searching folder or retrieving file metadata: {e}")
        raise

# Main function
def main():
    try:
        # Specify the vault path to search
        vault_path = "/obsidian/personal/01_daily"
        print(f"Searching for '_Journal' folder in: {vault_path}")
        find_journal_and_retrieve_metadata(vault_path)
    except EnvironmentError as e:
        print(f"Environment Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
