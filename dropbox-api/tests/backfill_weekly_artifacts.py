import os
import sys
import re
from datetime import datetime, timedelta
import dropbox
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

# Get the PROJECT_ROOT_PATH
PROJECT_ROOT_PATH = os.getenv('PROJECT_ROOT_PATH')

# Ensure the PROJECT_ROOT_PATH is set
if not PROJECT_ROOT_PATH:
    raise EnvironmentError("Error: PROJECT_ROOT_PATH environment variable not set")

# Construct the path to the .env file and load it
env_path = Path(PROJECT_ROOT_PATH) / '.env'
load_dotenv(dotenv_path=env_path)

# Retrieve the Dropbox access token from Redis
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()

# Initialize Dropbox client using the token from Redis
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

def find_weekly_folder(dropbox_vault_path):
    response = dbx.files_list_folder(dropbox_vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Weekly' in Dropbox")

def generate_weekly_content(sunday_date):
    """Generate weekly note content based on the given Sunday date"""
    
    # Parse the Sunday date from string to datetime object
    if isinstance(sunday_date, str):
        sunday_date = datetime.strptime(sunday_date, "%Y-%m-%d")
    
    # Calculate the preceding Monday (6 days before Sunday)
    preceding_monday = sunday_date - timedelta(days=6)
    
    # Format dates
    formatted_sunday = sunday_date.strftime("%Y-%m-%d")
    formatted_monday = preceding_monday.strftime("%Y-%m-%d")
    
    # Generate content with these dates
    file_content = f"""# Weekly Artifacts: {formatted_monday} to {formatted_sunday}

### Journal Entries
```dataview
LIST
FROM "01_Daily/_Journal"
WHERE 
date >= date("{formatted_monday}")
and date <= date("{formatted_sunday}")
SORT file.mtime DESC
```

### All Outgoing Links for the Week
```dataview
LIST
FROM outgoing([[{preceding_monday.strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]])
OR outgoing([[{sunday_date.strftime("%b %d, %Y")}]])
SORT file.mtime DESC
```

### All Incoming Links for the Week
```dataview
LIST
FROM [[{preceding_monday.strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]]
OR [[{sunday_date.strftime("%b %d, %Y")}]]
SORT file.mtime DESC
```

### Experiences / Events / Meetings / Sessions
**Outgoing Links:**
```dataview
LIST
FROM outgoing([[{preceding_monday.strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]])
OR outgoing([[{sunday_date.strftime("%b %d, %Y")}]])
WHERE contains(file.folder, "07_Experiences+Events+Meetings+Sessions")
SORT file.mtime DESC
```

**Incoming Links:**
```dataview
LIST
FROM [[{preceding_monday.strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]]
OR [[{sunday_date.strftime("%b %d, %Y")}]]
WHERE contains(file.folder, "07_Experiences+Events+Meetings+Sessions")
SORT file.mtime DESC
```

### CRM
**Outgoing Links:**
```dataview
LIST
FROM outgoing([[{preceding_monday.strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]])
OR outgoing([[{sunday_date.strftime("%b %d, %Y")}]])
WHERE contains(file.folder, "14_CRM")
SORT file.mtime DESC
```

**Incoming Links:**
```dataview
LIST
FROM [[{preceding_monday.strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]]
OR [[{sunday_date.strftime("%b %d, %Y")}]]
WHERE contains(file.folder, "14_CRM")
SORT file.mtime DESC
```

### Knowledge Hub
**Outgoing Links:**
```dataview
LIST
FROM outgoing([[{preceding_monday.strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]])
OR outgoing([[{sunday_date.strftime("%b %d, %Y")}]])
WHERE contains(file.folder, "05_Knowledge-Hub")
SORT file.mtime DESC
```

**Incoming Links:**
```dataview
LIST
FROM [[{preceding_monday.strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]]
OR [[{sunday_date.strftime("%b %d, %Y")}]]
WHERE contains(file.folder, "05_Knowledge-Hub")
SORT file.mtime DESC
```

### Writing
**Outgoing Links:**
```dataview
LIST
FROM outgoing([[{preceding_monday.strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]])
OR outgoing([[{sunday_date.strftime("%b %d, %Y")}]])
WHERE contains(file.folder, "03_Writing")
SORT file.mtime DESC
```

**Incoming Links:**
```dataview
LIST
FROM [[{preceding_monday.strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]]
OR [[{sunday_date.strftime("%b %d, %Y")}]]
WHERE contains(file.folder, "03_Writing")
SORT file.mtime DESC
```

### Notes & Ideas
**Outgoing Links:**
```dataview
LIST
FROM outgoing([[{preceding_monday.strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]])
OR outgoing([[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]])
OR outgoing([[{sunday_date.strftime("%b %d, %Y")}]])
WHERE contains(file.folder, "06_Notes+Ideas")
SORT file.mtime DESC
```

**Incoming Links:**
```dataview
LIST
FROM [[{preceding_monday.strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=1)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=2)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=3)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=4)).strftime("%b %d, %Y")}]]
OR [[{(preceding_monday + timedelta(days=5)).strftime("%b %d, %Y")}]]
OR [[{sunday_date.strftime("%b %d, %Y")}]]
WHERE contains(file.folder, "06_Notes+Ideas")
SORT file.mtime DESC
```
"""
    return file_content

def backfill_weekly_files(weekly_notes_folder_path):
    """Backfill content for all empty weekly note files"""
    
    print(f"Starting backfill process for folder: {weekly_notes_folder_path}")
    
    # List all files in the weekly notes folder
    response = dbx.files_list_folder(weekly_notes_folder_path)
    
    # Pattern to extract date from filenames like "Week-Ending-2024-06-02.md"
    date_pattern = re.compile(r'Week-Ending-(\d{4}-\d{2}-\d{2})\.md')
    
    # Process each file
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FileMetadata) and entry.name.endswith('.md'):
            # Extract date from filename
            match = date_pattern.match(entry.name)
            if match:
                sunday_date = match.group(1)
                file_path = f"{weekly_notes_folder_path}/{entry.name}"
                
                # Check if file is empty
                try:
                    file_metadata = dbx.files_get_metadata(file_path)
                    
                    # If file size is very small (basically empty)
                    if file_metadata.size < 10:  # Less than 10 bytes
                        print(f"File {entry.name} appears to be empty. Backfilling content...")
                        
                        # Download file to check actual content
                        try:
                            file_content = dbx.files_download(file_path)[1].content
                            content_str = file_content.decode('utf-8').strip()
                            
                            # If file is truly empty or just contains whitespace
                            if not content_str:
                                # Generate content based on the Sunday date
                                new_content = generate_weekly_content(sunday_date)
                                
                                # Upload the new content (requires delete first for overwrite)
                                dbx.files_delete_v2(file_path)
                                dbx.files_upload(new_content.encode('utf-8'), file_path)
                                print(f"Successfully backfilled content for {entry.name}")
                            else:
                                print(f"File {entry.name} is not empty. Skipping...")
                                
                        except Exception as e:
                            print(f"Error checking content of {entry.name}: {e}")
                    else:
                        print(f"File {entry.name} already has content ({file_metadata.size} bytes). Skipping...")
                        
                except Exception as e:
                    print(f"Error checking metadata for {entry.name}: {e}")
            else:
                print(f"File {entry.name} doesn't match expected pattern. Skipping...")
    
    print("Backfill process completed!")

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
            # Backfill existing weekly notes that are empty
            backfill_weekly_files(weekly_notes_folder_path)
        except dropbox.exceptions.ApiError as e:
            if isinstance(e.error, dropbox.files.GetMetadataError):
                raise FileNotFoundError("'_Weeks' subfolder not found")
            else:
                raise
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
