import os
import sys
from datetime import datetime, timedelta
import dropbox
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

def find_weekly_folder(dropbox_vault_path):
    response = dbx.files_list_folder(dropbox_vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Weekly' in Dropbox")

def fetch_last_review_number(health_review_folder_path):
    response = dbx.files_list_folder(health_review_folder_path)
    review_files = [entry.name for entry in response.entries if isinstance(entry, dropbox.files.FileMetadata) and entry.name.startswith("Weekly Health Review ")]
    if not review_files:
        return 0
    review_numbers = [int(f.split(" ")[3].split(" ")[0]) for f in review_files]
    return max(review_numbers)

def date_range_exists(health_review_folder_path, date_range):
    response = dbx.files_list_folder(health_review_folder_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FileMetadata) and date_range in entry.name:
            return True
    return False

def create_health_review_file(health_review_folder_path):
    last_review_number = fetch_last_review_number(health_review_folder_path)
    new_review_number = last_review_number + 1

    # Calculate the next Wednesday
    today = datetime.now()
    days_until_next_wednesday = (2 - today.weekday()) % 7
    if days_until_next_wednesday == 0:
        days_until_next_wednesday = 7
    next_wednesday = today + timedelta(days=days_until_next_wednesday)
    
    following_tuesday = next_wednesday + timedelta(days=6)
    
    formatted_wednesday = next_wednesday.strftime("%b. %d")
    formatted_tuesday = following_tuesday.strftime("%b. %d, %Y")

    # Create the file name and date range
    date_range = f"({formatted_wednesday} - {formatted_tuesday})"
    file_name = f"Weekly Health Review {new_review_number} {date_range}.md"
    dropbox_file_path = f"{health_review_folder_path}/{file_name}"

    # Check if a file with the same date range already exists
    if date_range_exists(health_review_folder_path, date_range):
        print(f"A file with the date range '{date_range}' already exists. Skipping creation.")
        return

    # Create the file with content
    try:
        file_content = f"Start Date: {next_wednesday.strftime('%Y-%m-%d')}\nEnd Date: {following_tuesday.strftime('%Y-%m-%d')}\n"
        dbx.files_upload(file_content.encode(), dropbox_file_path)
        print(f"Successfully created file '{file_name}' in Dropbox.")
    except dropbox.exceptions.ApiError as e:
        print(f"Error creating file: {e}")

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        sys.exit(1)

    try:
        weekly_folder_path = find_weekly_folder(dropbox_vault_path)
        health_review_folder_path = f"{weekly_folder_path}/_Weekly-Health-Review"
        try:
            dbx.files_get_metadata(health_review_folder_path)
        except dropbox.exceptions.ApiError as e:
            if isinstance(e.error, dropbox.files.GetMetadataError):
                raise FileNotFoundError("'_Weekly-Health-Review' subfolder not found")
            else:
                raise
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    create_health_review_file(health_review_folder_path)

if __name__ == "__main__":
    main()

