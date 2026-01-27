import os
import dropbox
from datetime import datetime, timedelta
import pytz
import redis
from dotenv import load_dotenv
from pathlib import Path
import logging
import argparse

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

def find_templates_folder(vault_path):
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Templates"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Templates' in the Obsidian vault")

def get_template_content(templates_folder):
    template_path = f"{templates_folder}/daily-templates/daily_note_properties.md"
    try:
        _, response = dbx.files_download(template_path)
        return response.content.decode('utf-8')
    except dropbox.exceptions.HttpError as e:
        print(f"Error retrieving template: {e}")
        print(f"Attempted to retrieve from path: {template_path}")
        return ""

def create_journal_file(journal_folder_path, vault_path, use_today=False):
    # Define timezone using environment variable
    system_tz = pytz.timezone(timezone_str)
    now_system = datetime.now(system_tz)
    days_offset = 0 if use_today else 1
    next_day = now_system + timedelta(days=days_offset)
    
    formatted_date = f"{next_day.strftime('%b')} {next_day.day}, {next_day.strftime('%Y')}"
    file_name = f"{formatted_date}.md"
    dropbox_file_path = f"{journal_folder_path}/{file_name}"

    try:
        dbx.files_get_metadata(dropbox_file_path)
        print(f"Journal file for '{formatted_date}' already exists. No new file created.")
    except dropbox.exceptions.ApiError as e:
        if isinstance(e.error, dropbox.files.GetMetadataError):
            print(f"File '{file_name}' does not exist in Dropbox. Creating it now.")
            
            # Find template folder and get template content
            templates_folder = find_templates_folder(vault_path)
            template_content = get_template_content(templates_folder)
            
            # Replace placeholders in the template
            filled_template = template_content.replace('{{date}}', formatted_date)
            
            # Upload the file with the filled template
            dbx.files_upload(filled_template.encode('utf-8'), dropbox_file_path)
            print(f"Successfully created file '{file_name}' in Dropbox using the template.")
        else:
            raise

def main():
    parser = argparse.ArgumentParser(description="Create daily journal file")
    parser.add_argument("--today", action="store_true", 
                       help="Create journal file for today instead of tomorrow")
    args = parser.parse_args()
    
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return
    try:
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        journal_folder_path = f"{daily_folder_path}/_Journal"
        create_journal_file(journal_folder_path, dropbox_vault_path, args.today)
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
