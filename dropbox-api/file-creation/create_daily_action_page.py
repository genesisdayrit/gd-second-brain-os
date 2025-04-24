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

def find_daily_folder(vault_path):
    """Search for the '_Daily' folder in the specified vault path."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily' in Dropbox")

def find_daily_action_folder(vault_path):
    """Search for the '_Daily-Action' folder inside the specified daily folder."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily-Action"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily-Action' in Dropbox")

def create_daily_action_file(daily_action_folder_path):
    """Create a new daily action file with structured prompts and two reflection questions."""
    # Define timezone using environment variable
    system_tz = pytz.timezone(timezone_str)
    now_system = datetime.now(system_tz)
    next_day = now_system + timedelta(days=1)
    
    # Format the file name as "DA YYYY-MM-DD"
    file_name = f"DA {next_day.strftime('%Y-%m-%d')}.md"
    dropbox_file_path = f"{daily_action_folder_path}/{file_name}"

    # Content structure with section prompts and questions
    content = (
        "Vision Objective 1:\n"
        "Vision Objective 2:\n"
        "Vision Objective 3:\n\n"
        "One thing that you can do to improve today:\n\n"
        "Mindset Objective:\n"
        "Body Objective:\n"
        "Social Objective:\n\n"
        "Gratitude:\n\n"
        "---\n\n"
        "What is the highest leverage thing that you can do today to move the ball forward on what you need to?\n"
        "If you only had 2 hours to work today, what would you need to get done to move forward towards your goals or master vision?"
    )

    try:
        # Check if the file already exists
        dbx.files_get_metadata(dropbox_file_path)
        print(f"Daily action file for '{next_day.strftime('%Y-%m-%d')}' already exists. No new file created.")
    except dropbox.exceptions.ApiError as e:
        if isinstance(e.error, dropbox.files.GetMetadataError):
            print(f"File '{file_name}' does not exist in Dropbox. Creating it now.")
            # Upload the file with the content
            dbx.files_upload(content.encode('utf-8'), dropbox_file_path)
            print(f"Successfully created daily action file '{file_name}' in Dropbox.")
        else:
            raise

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return
    try:
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        daily_action_folder_path = find_daily_action_folder(daily_folder_path)
        create_daily_action_file(daily_action_folder_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

