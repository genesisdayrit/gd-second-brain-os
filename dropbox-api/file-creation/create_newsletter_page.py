import os
import sys
from datetime import datetime, timedelta
import dropbox
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Get the PROJECT_ROOT_PATH
PROJECT_ROOT_PATH = os.getenv('PROJECT_ROOT_PATH')

# Ensure the PROJECT_ROOT_PATH is set
if not PROJECT_ROOT_PATH:
    raise EnvironmentError("Error: PROJECT_ROOT_PATH environment variable not set")

# Construct the path to the .env file and load it
env_path = Path(PROJECT_ROOT_PATH) / '.env'
load_dotenv(dotenv_path=env_path)

# Initialize Dropbox client
DROPBOX_ACCESS_TOKEN = os.getenv('DROPBOX_ACCESS_TOKEN')
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def find_weekly_folder(dropbox_vault_path):
    response = dbx.files_list_folder(dropbox_vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Weekly' in Dropbox")

def create_newsletter_file(newsletter_folder_path):
    # Calculate the Sunday after next upcoming Sunday
    today = datetime.now()
    days_until_next_sunday = (6 - today.weekday()) % 7
    if days_until_next_sunday == 0:  # If today is Sunday, set days_until_next_sunday to 7 to get the next Sunday
        days_until_next_sunday = 7
    second_upcoming_sunday = today + timedelta(days=days_until_next_sunday + 7)
    formatted_date = second_upcoming_sunday.strftime("%b. %d, %Y")

    # Create the file name
    file_name = f"Weekly Newsletter {formatted_date}.md"
    dropbox_file_path = f"{newsletter_folder_path}/{file_name}"

    # Check if the file already exists
    try:
        dbx.files_get_metadata(dropbox_file_path)
        print(f"File '{file_name}' already exists in Dropbox. Skipping creation.")
    except dropbox.exceptions.ApiError as e:
        if isinstance(e.error, dropbox.files.GetMetadataError):
            print(f"File '{file_name}' does not exist in Dropbox. Creating it now.")
            dbx.files_upload(b"", dropbox_file_path)  # Upload an empty bytes object
            print(f"Successfully created empty file '{file_name}' in Dropbox.")
        else:
            raise

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        sys.exit(1)

    try:
        weekly_folder_path = find_weekly_folder(dropbox_vault_path)
        newsletter_folder_path = f"{weekly_folder_path}/_Newsletters"
        try:
            dbx.files_get_metadata(newsletter_folder_path)
        except dropbox.exceptions.ApiError as e:
            if isinstance(e.error, dropbox.files.GetMetadataError):
                raise FileNotFoundError("'_Newsletters' subfolder not found")
            else:
                raise
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    create_newsletter_file(newsletter_folder_path)

if __name__ == "__main__":
    main()