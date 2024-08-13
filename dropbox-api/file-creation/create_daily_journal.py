import os
import dropbox
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(os.path.join(os.getenv('PROJECT_ROOT_PATH'), '.env'))

# Initialize Dropbox client
DROPBOX_ACCESS_TOKEN = os.getenv('DROPBOX_ACCESS_TOKEN')
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
            dbx.files_upload("", dropbox_file_path)
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
