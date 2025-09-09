import os
import dropbox
from datetime import datetime
import redis
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')  # Default to 'localhost' if not set
redis_port = int(os.getenv('REDIS_PORT', 6379))    # Default to 6379 if not set
redis_password = os.getenv('REDIS_PASSWORD', None)  # Default to None if not set

# Connect to Redis using the environment variables
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Function to get the Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Retrieve the Dropbox access token from Redis
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()

# Initialize Dropbox client using the token from Redis
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def find_daily_folder(vault_path):
    """Search for the '_Daily' folder in the specified vault path."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily' in Dropbox")

def find_daily_action_folder(vault_path):
    """Search for the '_Daily-Action' folder inside the specified daily folder."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily-Action"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily-Action' in Dropbox")

def parse_yaml_frontmatter(content):
    """
    Parse YAML frontmatter from markdown content.
    Returns a tuple of (yaml_section, main_content).
    """
    if not content.startswith('---\n'):
        # No YAML frontmatter found
        return "", content
    
    # Find the closing --- for YAML frontmatter
    lines = content.split('\n')
    yaml_end_index = -1
    
    for i, line in enumerate(lines[1:], 1):  # Start from line 1 (skip first ---)
        if line.strip() == '---':
            yaml_end_index = i
            break
    
    if yaml_end_index == -1:
        # No closing --- found, treat as no YAML frontmatter
        return "", content
    
    # Extract YAML section (including the --- delimiters)
    yaml_lines = lines[:yaml_end_index + 1]
    yaml_section = '\n'.join(yaml_lines) + '\n\n'
    
    # Extract main content (everything after the closing ---)
    main_content_lines = lines[yaml_end_index + 1:]
    main_content = '\n'.join(main_content_lines)
    
    # Remove leading newlines from main content
    main_content = main_content.lstrip('\n')
    
    return yaml_section, main_content

def add_daily_review_section(daily_action_folder_path):
    """Find today's file and add a 'Daily Review' section after YAML frontmatter."""
    # Get today's date to find the file
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    file_name = f"DA {today_date_str}.md"
    dropbox_file_path = f"{daily_action_folder_path}/{file_name}"

    # Define the 'Daily Review' content to be added after YAML frontmatter
    daily_review_content = (
        "Daily Review:\n\n"
        "Win 1:\n\n"
        "Win 2 (What part of today was easiest, most enjoyable, and most effective in the direction of my dream reality?):\n\n"
        "Win 3 (What proof from today demonstrates that my Master Vision is unfolding before my eyes? And how did I create this win for myself?):\n\n"
        "What did not go well today...\n"
        "Be as brief or as detailed as you like:\n\n"
        "What concrete steps will you take to improve and make your life easier?\n\n"
        "Lastly, what are a few things you are grateful for?\n"
        "Think of something new or different than usual!\n\n"
        "---\n\n"
    )

    try:
        # Download the file's current content
        _, response = dbx.files_download(dropbox_file_path)
        current_content = response.content.decode('utf-8')
        
        # Parse YAML frontmatter and main content
        yaml_section, main_content = parse_yaml_frontmatter(current_content)
        
        # Check if daily review section already exists
        if "Daily Review:" in current_content:
            print(f"Daily Review section already exists in '{file_name}'. No changes made.")
            return
        
        # Combine YAML frontmatter + Daily Review + main content
        updated_content = yaml_section + daily_review_content + main_content

        # Upload the updated content back to Dropbox, overwriting the original file
        dbx.files_upload(updated_content.encode('utf-8'), dropbox_file_path, mode=dropbox.files.WriteMode.overwrite)
        print(f"Successfully added 'Daily Review' section to '{file_name}' after YAML frontmatter.")
        
    except dropbox.exceptions.ApiError as e:
        print(f"Error: Could not find today's file '{file_name}' in Dropbox.")
        raise e

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return
    try:
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        daily_action_folder_path = find_daily_action_folder(daily_folder_path)
        add_daily_review_section(daily_action_folder_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

