import os
import sys
from datetime import datetime, timedelta
import pytz
import dropbox
import redis
from dotenv import load_dotenv
from pathlib import Path

# Load the PROJECT_ROOT_PATH from environment and set up .env path
PROJECT_ROOT_PATH = os.getenv('PROJECT_ROOT_PATH')
if not PROJECT_ROOT_PATH:
    raise EnvironmentError("Error: PROJECT_ROOT_PATH environment variable not set")

# Load environment variables from .env file in PROJECT_ROOT_PATH
env_path = Path(PROJECT_ROOT_PATH) / '.env'
load_dotenv(dotenv_path=env_path)

# Set up Redis connection using environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)
redis_client = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Function to retrieve Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = redis_client.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Retrieve the Dropbox access token from Redis
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()

# Initialize Dropbox client using the token from Redis
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def find_weekly_folder(base_path):
    """Finds the folder ending with '_Weekly' in the base path."""
    for item in os.listdir(base_path):
        if item.endswith("_Weekly") and os.path.isdir(os.path.join(base_path, item)):
            return item
    raise FileNotFoundError("Could not find a folder ending with '_Weekly'")

def get_next_sunday():
    """Calculates the date for the Sunday after the upcoming Sunday."""
    today = datetime.now(pytz.timezone('US/Central'))
    days_until_sunday = (6 - today.weekday()) % 7  # Calculate days until the next Sunday
    next_sunday = today + timedelta(days=days_until_sunday)
    sunday_after_next = next_sunday + timedelta(days=7)
    return sunday_after_next.strftime("%Y-%m-%d")

def get_template_content(templates_folder):
    """Retrieves the content of the weekly map template."""
    template_path = f"{templates_folder}/weekly-templates/weekly_map_template_w_placeholder.md"
    try:
        _, response = dbx.files_download(template_path)
        return response.content.decode('utf-8')
    except dropbox.exceptions.HttpError as e:
        print(f"Error retrieving template: {e}")
        print(f"Attempted to retrieve from path: {template_path}")
        return ""

def create_weekly_map_file(file_path, title_date, template_content):
    """Creates a Weekly Map file with the provided template content if it does not already exist."""
    file_name = f"Weekly Map {title_date}.md"
    full_file_path = os.path.join(file_path, file_name)

    # Check if the file already exists
    if os.path.exists(full_file_path):
        print(f"File '{file_name}' already exists. Skipping creation.")
        return

    # Create the file with template content
    try:
        with open(full_file_path, 'w') as file:
            file.write(template_content)
        print(f"Successfully created file '{file_name}' with template content.")
    except IOError as e:
        print(f"Error creating file: {e}")

def main():
    # Retrieve paths from environment variables
    base_path = os.getenv('OBSIDIAN_VAULT_BASE_PATH')
    templates_folder = os.getenv('TEMPLATES_FOLDER_PATH')
    
    if not base_path or not templates_folder:
        print("Error: Required environment variables (OBSIDIAN_VAULT_BASE_PATH or TEMPLATES_FOLDER_PATH) not set.")
        sys.exit(1)

    try:
        # Find the '_Weekly' folder and then the '_Weekly-Maps' subfolder
        weekly_folder = find_weekly_folder(base_path)
        weekly_maps_path = os.path.join(base_path, weekly_folder, "_Weekly-Maps")
        
        if not os.path.exists(weekly_maps_path):
            raise FileNotFoundError("'_Weekly-Maps' subfolder not found")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Get the title date for the file
    title_date = get_next_sunday()
    
    # Retrieve the template content
    template_content = get_template_content(templates_folder)
    
    # Create the Weekly Map file with the template content
    create_weekly_map_file(weekly_maps_path, title_date, template_content)

if __name__ == "__main__":
    main()
