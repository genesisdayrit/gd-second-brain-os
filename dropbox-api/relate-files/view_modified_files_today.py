import os
import dropbox
import redis
from dotenv import load_dotenv
from datetime import datetime
import pytz
import logging

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
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

# Function to load paths from a separate file
def load_paths(file_path):
    try:
        with open(file_path, 'r') as f:
            paths = [line.strip() for line in f.readlines() if line.strip()]
        return paths
    except FileNotFoundError:
        print(f"Error: Paths file '{file_path}' not found.")
        return []

# Function to check if files in a folder were client modified today
def get_modified_files_today(paths):
    modified_files = []
    today = datetime.now(pytz.timezone(timezone_str)).date()

    for path in paths:
        try:
            print(f"Checking path: {path}")
            response = dbx.files_list_folder(path)
            
            # Check all files in the folder
            while True:
                for entry in response.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        client_modified_date = entry.client_modified.date()
                        if client_modified_date == today:
                            modified_files.append(entry.path_lower)

                if not response.has_more:
                    break
                response = dbx.files_list_folder_continue(response.cursor)

        except dropbox.exceptions.ApiError as e:
            print(f"Error accessing path {path}: {e}")

    return modified_files

# Main function
def main():
    paths_file = "paths_to_check.txt"  # File containing the list of paths to check
    paths_to_check = load_paths(paths_file)

    if not paths_to_check:
        print("No paths to check. Please ensure the paths file is correctly populated.")
        return

    modified_files = get_modified_files_today(paths_to_check)

    if modified_files:
        print("Files modified today:")
        for file in modified_files:
            print(file)
    else:
        print("No files were modified today.")

if __name__ == "__main__":
    main()
