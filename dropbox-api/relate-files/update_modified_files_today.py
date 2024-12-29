import os
import dropbox
import redis
from dotenv import load_dotenv
from datetime import datetime
import pytz
import logging
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

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
        logger.error(f"Error: Paths file '{file_path}' not found.")
        return []

# Function to check if files in a folder were client modified today
def get_modified_files_today(paths):
    modified_files = []
    today = datetime.now(pytz.timezone('US/Eastern')).date()

    for path in paths:
        try:
            logger.info(f"Checking path: {path}")
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
            logger.error(f"Error accessing path {path}: {e}")

    return modified_files

# Function to update or add a journal property in the metadata of a file
def update_journal_property(file_path):
    try:
        metadata, response = dbx.files_download(file_path)
        content = response.content.decode('utf-8')
        original_file_name = metadata.name  # Preserve the original file name
        original_path_display = metadata.path_display  # Preserve the original path display
        client_modified = metadata.client_modified
        formatted_date = client_modified.strftime("%b %-d, %Y")

        # Extract metadata section
        properties_match = re.search(r'---(.*?)---', content, re.DOTALL)
        if properties_match:
            properties_section = properties_match.group(1)

            # Check if the formatted_date exists anywhere in properties
            if f"[[{formatted_date}]]" in properties_section:
                logger.info(f"Date [[{formatted_date}]] already exists in properties for file: {file_path}")
                return

            # Check for existing Journal property
            journal_match = re.search(r'Journal:\s*(.*?)(?=\n\S|$)', properties_section, re.DOTALL)
            if journal_match:
                # Parse existing journal entries
                journal_entries = journal_match.group(1).splitlines()
                # Detect indentation from the first entry
                indentation = " " * (len(journal_entries[0]) - len(journal_entries[0].lstrip())) if journal_entries else "    "

                # Add the new date entry under the Journal property
                formatted_date_entry = f"{indentation}- \"[[{formatted_date}]]\""
                journal_entries.append(formatted_date_entry)
                updated_journal = "Journal:\n" + "\n".join(journal_entries)
                updated_properties = re.sub(r'Journal:\s*(.*?)(?=\n\S|$)', updated_journal, properties_section, flags=re.DOTALL)

            else:
                # Add Journal property if it doesn't exist
                updated_properties = properties_section + f"\nJournal:\n    - \"[[{formatted_date}]]\""

            # Ensure the closing --- is on a new line
            updated_content = f"---\n{updated_properties.strip()}\n---\n{content.split('---', 2)[2].strip()}"

        else:
            # Add a new metadata section if none exists
            updated_content = (
                f"---\nJournal:\n    - \"[[{formatted_date}]]\"\n---\n{content}"
            )

        # Upload the updated content back to Dropbox using the original file name and path
        dbx.files_upload(updated_content.encode('utf-8'), original_path_display, mode=dropbox.files.WriteMode.overwrite)
        logger.info(f"Updated Journal property for file: {original_file_name}")

    except Exception as e:
        logger.error(f"Error updating file {file_path}: {e}")

# Main function
def main():
    logger.info("Starting script to check modified files and update Journal property.")

    paths_file = "paths_to_check.txt"  # File containing the list of paths to check
    paths_to_check = load_paths(paths_file)

    if not paths_to_check:
        logger.error("No paths to check. Please ensure the paths file is correctly populated.")
        return

    modified_files = get_modified_files_today(paths_to_check)

    if modified_files:
        logger.info("Files modified today:")
        for file_path in modified_files:
            logger.info(f"Processing file: {file_path}")
            update_journal_property(file_path)
    else:
        logger.info("No files were modified today.")

if __name__ == "__main__":
    main()
