import os
import dropbox
import redis
import yaml  # Install with `pip install pyyaml`
from datetime import datetime
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

# Redis configuration
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Get Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Initialize Dropbox client
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def get_today_filename():
    """ Format today's date to match the journal filename format. """
    today = datetime.now(pytz.timezone('US/Eastern'))
    return today.strftime('%b %-d, %Y.md')  # Linux/macOS formatting

def get_today_iso_date():
    """ Returns today's date in YYYY-MM-DD format. """
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')

def find_today_journal_entry(journal_folder):
    """ Locate today's journal entry inside the '_Journal' folder. """
    try:
        today_filename = get_today_filename()
        all_files = []
        response = dbx.files_list_folder(journal_folder)

        # Retrieve all files, handling pagination
        while True:
            all_files.extend(response.entries)
            if not response.has_more:
                break
            response = dbx.files_list_folder_continue(response.cursor)

        # Search for today's journal file (case-insensitive)
        for entry in all_files:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower() == today_filename.lower():
                print(f"Found today's journal file: {entry.name}")
                return entry.path_lower, entry.name  # Preserve original filename casing

        raise FileNotFoundError(f"No journal file found for today's date ({today_filename}) in '{journal_folder}'")
    except dropbox.exceptions.ApiError as e:
        print(f"Error fetching journal files: {e}")
        raise

def retrieve_file_content(file_path):
    """ Retrieve the content of a Markdown file from Dropbox. """
    try:
        _, response = dbx.files_download(file_path)
        return response.content.decode('utf-8')
    except dropbox.exceptions.ApiError as e:
        print(f"Error downloading file: {e}")
        return None

def extract_yaml_metadata(file_content):
    """ Extract YAML front matter from a Markdown file while preserving key order. """
    lines = file_content.splitlines()
    if lines[0] == "---":
        yaml_lines = []
        content_start = None

        for i, line in enumerate(lines[1:], 1):
            if line == "---":  
                content_start = i + 1
                break
            yaml_lines.append(line)

        yaml_str = "\n".join(yaml_lines)
        try:
            metadata = yaml.safe_load(yaml_str) or {}
            metadata_ordered = {key: metadata[key] for key in yaml.safe_load(yaml_str)}
            remaining_content = "\n".join(lines[content_start:]) if content_start else ""
            return metadata_ordered, remaining_content
        except yaml.YAMLError as e:
            print(f"Error parsing YAML: {e}")
            return None, None
    return None, file_content

def update_yaml_metadata(metadata):
    """ Ensure the 'Date' field is set in the metadata while preserving order. """
    if 'Date' not in metadata or not metadata['Date']:
        metadata['Date'] = get_today_iso_date()
        print(f"Updated Date field to: {metadata['Date']}")
    return metadata

def save_updated_file(file_path, file_name, updated_metadata, content):
    """ Convert updated metadata back to YAML, merge with content, and upload to Dropbox. """
    yaml_str = yaml.safe_dump(updated_metadata, default_flow_style=False, sort_keys=False)  # Preserve key order
    new_file_content = f"---\n{yaml_str}---\n{content}"

    try:
        upload_path = os.path.join(os.path.dirname(file_path), file_name)  # Keep original filename casing
        dbx.files_upload(
            new_file_content.encode('utf-8'),
            upload_path,
            mode=dropbox.files.WriteMode.overwrite
        )
        print(f"Updated file uploaded successfully: {upload_path}")
    except dropbox.exceptions.ApiError as e:
        print(f"Error uploading file: {e}")

def main():
    dropbox_vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set")
        return

    try:
        journal_folder_path = dropbox_vault_path + "/01_Daily/_Journal"
        today_journal_entry, original_filename = find_today_journal_entry(journal_folder_path)
        print(f"Today's journal entry is located at: {today_journal_entry}")

        file_content = retrieve_file_content(today_journal_entry)
        if not file_content:
            print("Error: Unable to retrieve journal file content.")
            return

        metadata, remaining_content = extract_yaml_metadata(file_content)
        if metadata is None:
            print("No valid YAML metadata found.")
            return

        # Update metadata while preserving order
        updated_metadata = update_yaml_metadata(metadata)

        # Save the updated file back to Dropbox
        save_updated_file(today_journal_entry, original_filename, updated_metadata, remaining_content)

    except FileNotFoundError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

