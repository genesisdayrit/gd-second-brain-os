import os
import dropbox
from dotenv import load_dotenv

# Load the PROJECT_ROOT_PATH environment variable
project_root = os.getenv('PROJECT_ROOT_PATH')

# Check if PROJECT_ROOT_PATH is set
if not project_root:
    raise EnvironmentError("Error: PROJECT_ROOT_PATH environment variable not set")

# Construct the path to the .env file and load it
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

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
