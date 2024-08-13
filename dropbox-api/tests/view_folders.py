import os
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

# Set up Dropbox access token
DROPBOX_ACCESS_TOKEN = os.getenv('DROPBOX_ACCESS_TOKEN')

# Initialize Dropbox client
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def list_folders(path=""):
    try:
        response = dbx.files_list_folder(path)
        print("Folders in your Dropbox:")
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                print(f"- {entry.name}")
    except dropbox.exceptions.ApiError as e:
        print(f"Error: {e}")

def main():
    list_folders()

if __name__ == "__main__":
    main()