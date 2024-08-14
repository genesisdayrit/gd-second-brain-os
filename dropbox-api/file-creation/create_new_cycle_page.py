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

# The rest of the script remains unchanged
def find_cycles_folder(dropbox_vault_path):
    response = dbx.files_list_folder(dropbox_vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Cycles"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Cycles' in Dropbox")

def fetch_last_cycle_number(cycles_folder_path):
    response = dbx.files_list_folder(cycles_folder_path)
    cycle_files = [entry.name for entry in response.entries if isinstance(entry, dropbox.files.FileMetadata) and entry.name.startswith("Cycle ")]
    if not cycle_files:
        return 0
    cycle_numbers = [int(f.split(" ")[1].split(" ")[0]) for f in cycle_files]
    return max(cycle_numbers)

def date_range_exists(cycles_folder_path, date_range):
    response = dbx.files_list_folder(cycles_folder_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FileMetadata) and date_range in entry.name:
            return True
    return False

def create_cycle_file(cycles_folder_path):
    last_cycle_number = fetch_last_cycle_number(cycles_folder_path)
    new_cycle_number = last_cycle_number + 1

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
    file_name = f"Cycle {new_cycle_number} {date_range}.md"
    dropbox_file_path = f"{cycles_folder_path}/{file_name}"

    # Check if a file with the same date range already exists
    if date_range_exists(cycles_folder_path, date_range):
        print(f"A file with the date range '{date_range}' already exists. Skipping creation.")
        return

    # Create the file with content
    try:
        file_content = f"Cycle Start Date: {next_wednesday.strftime('%Y-%m-%d')}\nCycle End Date: {following_tuesday.strftime('%Y-%m-%d')}\n"
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
        cycles_folder_path = find_cycles_folder(dropbox_vault_path)
        weekly_cycles_folder_path = f"{cycles_folder_path}/_Weekly-Cycles"
        try:
            dbx.files_get_metadata(weekly_cycles_folder_path)
        except dropbox.exceptions.ApiError as e:
            if isinstance(e.error, dropbox.files.GetMetadataError):
                raise FileNotFoundError("'_Weekly-Cycles' subfolder not found")
            else:
                raise
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    create_cycle_file(weekly_cycles_folder_path)

if __name__ == "__main__":
    main()