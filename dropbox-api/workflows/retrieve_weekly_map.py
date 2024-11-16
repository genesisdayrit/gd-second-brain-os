import os
import re
import dropbox
import redis
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

def get_dropbox_access_token():
    """Retrieve the Dropbox access token from Redis."""
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

def find_weekly_folder(vault_path):
    """Search for a folder ending with '_Weekly' in the specified vault path."""
    result = dbx.files_list_folder(vault_path)
    for entry in result.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Weekly' in Dropbox")

def find_weekly_maps_folder(weekly_folder_path):
    """Search for the '_Weekly-Maps' folder inside the '_Weekly' folder."""
    result = dbx.files_list_folder(weekly_folder_path)
    for entry in result.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly-Maps"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Weekly-Maps' in Dropbox")

def list_all_files_in_folder(folder_path):
    """List all files in the specified folder, including pagination."""
    all_files = []
    result = dbx.files_list_folder(folder_path)

    while True:
        all_files.extend(result.entries)
        if not result.has_more:
            break
        result = dbx.files_list_folder_continue(result.cursor)

    return all_files

def find_this_weeks_map(files):
    """Find this week's map file based on today's date."""
    today = datetime.now()
    # Calculate the next Sunday
    days_until_sunday = (6 - today.weekday()) % 7
    next_sunday = today + timedelta(days=days_until_sunday)
    sunday_str = next_sunday.strftime("%Y-%m-%d").lower()  # Ensure lowercase comparison

    # Search for the file with the week's ending date
    for file in files:
        if isinstance(file, dropbox.files.FileMetadata) and f"weekly map {sunday_str}" in file.name.lower():
            return file

    return None

def download_file_content(file_metadata):
    """Download the content of a file from Dropbox."""
    _, response = dbx.files_download(file_metadata.path_lower)
    return response.content.decode("utf-8")

def extract_section_from_content(content, start_marker, end_marker):
    """Extract a specific section from the content using start and end markers."""
    try:
        start_index = content.index(start_marker)
        end_index = content.index(end_marker, start_index)
        return content[start_index:end_index].strip()
    except ValueError:
        return None

def parse_section_content(section):
    """Parse the section content and extract goals and objectives."""
    goals_and_objectives = {}

    # Extract Yearly Goal
    yearly_goal_match = re.search(r"\*\*Yearly Goal:\*\*\s*-\s*(.+)", section)
    if yearly_goal_match:
        goals_and_objectives["Yearly Goal"] = yearly_goal_match.group(1).strip()

    # Extract Monthly Goal
    monthly_goal_match = re.search(r"\*\*Monthly Goal:\*\*\s*-\s*(.+)", section)
    if monthly_goal_match:
        goals_and_objectives["Monthly Goal"] = monthly_goal_match.group(1).strip()

    # Extract Vision Objectives
    vision_objectives = []
    vision_objective_matches = re.findall(r"\*\*THIS WEEK: Vision objective #\d+:\*\*.*?\n-\s*(.*?)\n", section, re.DOTALL)
    for obj in vision_objective_matches:
        vision_objectives.append(obj.strip())
    goals_and_objectives["Vision Objectives"] = vision_objectives

    # Extract Mindset, Body, and Social Goals
    for key in ["Mindset goal", "Body goal", "Social goal"]:
        match = re.search(rf"\*\*THIS WEEK - {key}:\*\*\s*-\s*(.*)", section)
        if match:
            goals_and_objectives[key.capitalize()] = match.group(1).strip()

    return goals_and_objectives

def main():
    try:
        # Retrieve Dropbox access token from Redis
        dropbox_access_token = get_dropbox_access_token()

        # Initialize Dropbox client
        global dbx
        dbx = dropbox.Dropbox(dropbox_access_token)

        # Get the Dropbox vault path from the environment variable
        vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
        if not vault_path:
            raise EnvironmentError("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set.")

        # Locate the _Weekly folder
        weekly_folder_path = find_weekly_folder(vault_path)
        print(f"Found _Weekly folder at: {weekly_folder_path}")

        # Locate the _Weekly-Maps folder inside _Weekly
        weekly_maps_folder_path = find_weekly_maps_folder(weekly_folder_path)
        print(f"Found _Weekly-Maps folder at: {weekly_maps_folder_path}")

        # List all files in the _Weekly-Maps folder
        all_files = list_all_files_in_folder(weekly_maps_folder_path)
        print("Searching for this week's map...")

        # Find this week's map
        this_weeks_map = find_this_weeks_map(all_files)
        if not this_weeks_map:
            print("This week's map could not be found.")
            return

        print(f"This week's map found: {this_weeks_map.name}")

        # Download and parse the file content
        file_content = download_file_content(this_weeks_map)

        # Extract the section from the content
        start_marker = "Review North Star Goals..."
        end_marker = "---"
        section = extract_section_from_content(file_content, start_marker, end_marker)

        if not section:
            print("The specified section could not be found in the file.")
            return

        # Parse and extract the goals and objectives
        parsed_content = parse_section_content(section)

        # Output the parsed content
        print("Parsed Content:")
        for key, value in parsed_content.items():
            if isinstance(value, list):
                print(f"{key}:")
                for idx, item in enumerate(value, start=1):
                    print(f"  {idx}. {item}")
            else:
                print(f"{key}: {value}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except EnvironmentError as e:
        print(f"Environment Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

