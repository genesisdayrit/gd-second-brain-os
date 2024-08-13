import os
import dropbox
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(os.path.join(os.getenv('PROJECT_ROOT_PATH'), '.env'))

# Initialize Dropbox client
DROPBOX_ACCESS_TOKEN = os.getenv('DROPBOX_ACCESS_TOKEN')
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def list_vault_contents():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return

    try:
        response = dbx.files_list_folder(dropbox_vault_path)
        print(f"Contents of '{dropbox_vault_path}':")
        for entry in response.entries:
            print(f"- {entry.name}")
    except dropbox.exceptions.ApiError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_vault_contents()

