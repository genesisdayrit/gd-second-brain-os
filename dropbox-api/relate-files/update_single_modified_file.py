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
    logger.info("Starting script to update Journal property.")

    # Ask user for file path
    file_path = input("Enter the file path to update: ").strip()

    if not file_path:
        logger.error("No file path provided. Exiting.")
        return

    # Update Journal property for the provided file
    update_journal_property(file_path)

if __name__ == "__main__":
    main()
