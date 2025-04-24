import os
import dropbox
import redis
import yaml  # Install with `pip install pyyaml`
from datetime import datetime
from dotenv import load_dotenv
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

# Initialize Dropbox client
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def get_today_filename():
    """
    Format today's date to match the journal filename format.
    Example: 'Feb 9, 2025.md'
    """
    today = datetime.now(pytz.timezone(timezone_str))
    return today.strftime('%b %-d, %Y.md')  # Linux/macOS formatting

def find_daily_folder(vault_path):
    """
    Locate the '_Daily' folder inside the user's Dropbox Obsidian vault.
    """
    try:
        response = dbx.files_list_folder(vault_path)
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and '_daily' in entry.name.lower():
                print(f"Found Daily folder: {entry.name}")
                return entry.path_lower
        raise FileNotFoundError(f"No folder found with '_Daily' in '{vault_path}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching folder list: {e}")
        raise

def find_journal_folder(daily_folder_path):
    """
    Locate the '_Journal' folder inside the '_Daily' folder.
    """
    try:
        response = dbx.files_list_folder(daily_folder_path)
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and '_journal' in entry.name.lower():
                print(f"Found Journal folder: {entry.name}")
                return entry.path_lower
        raise FileNotFoundError(f"No folder found with '_Journal' in '{daily_folder_path}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching folder list: {e}")
        raise

def find_today_journal_entry(journal_folder):
    """
    Locate today's journal entry inside the '_Journal' folder.
    """
    try:
        today_filename = get_today_filename()
        all_files = []
        response = dbx.files_list_folder(journal_folder)

        # Retrieve all files, handling pagination
        while True:
            all_files.extend(response.entries)
            if not response.has_more:
                break
            response = dbx.files_list_folder_continue(response.cursor)

        # Search for today's journal file
        for entry in all_files:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower() == today_filename.lower():
                print(f"Found today's journal file: {entry.name}")
                return entry.path_lower

        raise FileNotFoundError(f"No journal file found for today's date ({today_filename}) in '{journal_folder}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching journal files: {e}")
        raise

def extract_yaml_metadata(file_content):
    """
    Extract YAML front matter from a Markdown file and return it as a dictionary.
    """
    lines = file_content.splitlines()
    if lines[0] == "---":
        yaml_lines = []
        for line in lines[1:]:
            if line == "---":  # End of YAML metadata
                break
            yaml_lines.append(line)
        
        yaml_str = "\n".join(yaml_lines)
        try:
            return yaml.safe_load(yaml_str)  # Parse YAML
        except yaml.YAMLError as e:
            print(f"Error parsing YAML: {e}")
            return None
    return None  # No valid YAML front matter found

def retrieve_file_content(file_path):
    """
    Retrieve the content of a Markdown file from Dropbox.
    """
    try:
        _, response = dbx.files_download(file_path)
        return response.content.decode('utf-8')
    except dropbox.exceptions.ApiError as e:
        print(f"Error downloading file: {e}")
        return None

def main():
    # Base Dropbox path for the Obsidian vault
    dropbox_vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set")
        return

    try:
        # Locate the _Daily folder
        daily_folder_path = find_daily_folder(dropbox_vault_path)

        # Locate the _Journal folder inside _Daily
        journal_folder_path = find_journal_folder(daily_folder_path)

        # Find today's journal entry
        today_journal_entry = find_today_journal_entry(journal_folder_path)

        print(f"Today's journal entry is located at: {today_journal_entry}")

        # Retrieve file content
        file_content = retrieve_file_content(today_journal_entry)
        if not file_content:
            print("Error: Unable to retrieve journal file content.")
            return

        # Extract YAML metadata
        metadata = extract_yaml_metadata(file_content)
        if metadata:
            print("Extracted Metadata:")
            for key, value in metadata.items():
                print(f"{key}: {value}")
        else:
            print("No valid YAML metadata found.")

    except FileNotFoundError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

