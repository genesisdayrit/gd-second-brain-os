import os
import sys
from datetime import datetime, timedelta
import dropbox
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(os.path.join(os.getenv('PROJECT_ROOT_PATH'), '.env'))

# Initialize Dropbox client
DROPBOX_ACCESS_TOKEN = os.getenv('DROPBOX_ACCESS_TOKEN')
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def find_weekly_folder(dropbox_vault_path):
    response = dbx.files_list_folder(dropbox_vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Weekly' in Dropbox")

def create_weekly_file(weekly_notes_folder_path):
    # Calculate the nearest upcoming Sunday
    today = datetime.now()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:  # If today is Sunday, set days_until_sunday to 7 to get the next Sunday
        days_until_sunday = 7
    upcoming_sunday = today + timedelta(days=days_until_sunday)
    formatted_date = upcoming_sunday.strftime("%Y-%m-%d")

    # Create the file name
    file_name = f"Week-Ending-{formatted_date}.md"
    dropbox_file_path = f"{weekly_notes_folder_path}/{file_name}"

    # Check if the file already exists
    try:
        dbx.files_get_metadata(dropbox_file_path)
        print(f"File '{file_name}' already exists in Dropbox. Skipping creation.")
    except dropbox.exceptions.ApiError as e:
        if isinstance(e.error, dropbox.files.GetMetadataError):
            print(f"File '{file_name}' does not exist in Dropbox. Creating it now.")
            dbx.files_upload("", dropbox_file_path)
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
        weekly_notes_folder_path = f"{weekly_folder_path}/_Weeks"
        try:
            dbx.files_get_metadata(weekly_notes_folder_path)
        except dropbox.exceptions.ApiError as e:
            if isinstance(e.error, dropbox.files.GetMetadataError):
                raise FileNotFoundError("'_Weeks' subfolder not found")
            else:
                raise
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    create_weekly_file(weekly_notes_folder_path)

if __name__ == "__main__":
    main()
