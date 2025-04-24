import os
import dropbox
from datetime import datetime, timedelta
import pytz
import redis
from dotenv import load_dotenv
from pathlib import Path
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

def find_weekly_folder(vault_path):
    """Search for the '_Weekly' folder in the specified vault path."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Weekly' in Dropbox")

def find_templates_folder(vault_path):
    """Search for the '_Templates' folder inside the specified vault path."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Templates"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Templates' in the Obsidian vault")

def get_template_content(templates_folder):
    """Retrieves the content of the weekly map template."""
    template_path = f"{templates_folder}/weekly-templates/weekly_map_template_w_placeholder.md"
    try:
        _, response = dbx.files_download(template_path)
        return response.content.decode('utf-8')
    except dropbox.exceptions.HttpError as e:
        print(f"Error retrieving template: {e}")
        print(f"Attempted to retrieve from path: {template_path}")
        return ""

def create_weekly_map_file(weekly_maps_folder_path, title_date, template_content):
    """Creates a Weekly Map file with the provided template content if it does not already exist."""
    file_name = f"Weekly Map {title_date}.md"
    dropbox_file_path = f"{weekly_maps_folder_path}/{file_name}"

    try:
        # Check if the file already exists
        dbx.files_get_metadata(dropbox_file_path)
        print(f"Weekly map file for '{title_date}' already exists. No new file created.")
    except dropbox.exceptions.ApiError as e:
        if isinstance(e.error, dropbox.files.GetMetadataError):
            print(f"File '{file_name}' does not exist in Dropbox. Creating it now.")
            # Upload the file with the content from the template
            dbx.files_upload(template_content.encode('utf-8'), dropbox_file_path)
            print(f"Successfully created weekly map file '{file_name}' in Dropbox.")
        else:
            raise

def main():
    # Retrieve Dropbox Obsidian vault path from environment variable
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return

    try:
        # Find the '_Weekly' folder and then the '_Weekly-Maps' subfolder
        weekly_folder_path = find_weekly_folder(dropbox_vault_path)
        weekly_maps_folder_path = f"{weekly_folder_path}/_Weekly-Maps"

        # Find the '_Templates' folder
        templates_folder_path = find_templates_folder(dropbox_vault_path)

        # Retrieve the template content from the '_Templates' folder
        template_content = get_template_content(templates_folder_path)

        # Calculate the title date for the file (Sunday after the upcoming Sunday)
        system_tz = pytz.timezone(timezone_str)
        today = datetime.now(system_tz)
        days_until_sunday = (6 - today.weekday()) % 7
        next_sunday = today + timedelta(days=days_until_sunday)
        sunday_after_next = next_sunday + timedelta(days=7)
        title_date = sunday_after_next.strftime("%Y-%m-%d")

        # Create the Weekly Map file with the template content
        create_weekly_map_file(weekly_maps_folder_path, title_date, template_content)

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
