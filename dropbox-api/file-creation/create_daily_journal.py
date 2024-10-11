import os
import dropbox
from datetime import datetime, timedelta
import pytz
import redis
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')  # Default to 'localhost' if not set
redis_port = int(os.getenv('REDIS_PORT', 6379))    # Default to 6379 if not set
redis_password = os.getenv('REDIS_PASSWORD', None)  # Default to None if not set

# Connect to Redis using the environment variables
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Function to get the Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Get the PROJECT_ROOT_PATH
PROJECT_ROOT_PATH = os.getenv('PROJECT_ROOT_PATH')

# Ensure the PROJECT_ROOT_PATH is set
if not PROJECT_ROOT_PATH:
    raise EnvironmentError("Error: PROJECT_ROOT_PATH environment variable not set")

# Construct the path to the .env file and load it
env_path = Path(PROJECT_ROOT_PATH) / '.env'
load_dotenv(dotenv_path=env_path)

# Retrieve the Dropbox access token from Redis
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()

# Initialize Dropbox client using the token from Redis
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def find_daily_folder(vault_path):
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily' in Dropbox")

def fetch_last_journal_date(journal_folder_path):
    response = dbx.files_list_folder(journal_folder_path)
    journal_files = [entry.name for entry in response.entries if isinstance(entry, dropbox.files.FileMetadata)]
    if not journal_files:
        return None
    return max(journal_files).split('.md')[0]

def create_journal_file(journal_folder_path):
    # Define timezone for Central Time
    central_tz = pytz.timezone('US/Central')
    now_central = datetime.now(central_tz)
    next_day = now_central + timedelta(days=1)
    
    formatted_date = f"{next_day.strftime('%b')} {next_day.day}, {next_day.strftime('%Y')}"
    file_name = f"{formatted_date}.md"
    dropbox_file_path = f"{journal_folder_path}/{file_name}"

    try:
        dbx.files_get_metadata(dropbox_file_path)
        print(f"Journal file for '{formatted_date}' already exists. No new file created.")
    except dropbox.exceptions.ApiError as e:
        if isinstance(e.error, dropbox.files.GetMetadataError):
            print(f"File '{file_name}' does not exist in Dropbox. Creating it now.")
            dbx.files_upload(b"", dropbox_file_path)  # Upload an empty bytes object
            print(f"Successfully created file '{file_name}' in Dropbox.")
        else:
            raise

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return

    try:
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        journal_folder_path = f"{daily_folder_path}/_Journal"
        create_journal_file(journal_folder_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

