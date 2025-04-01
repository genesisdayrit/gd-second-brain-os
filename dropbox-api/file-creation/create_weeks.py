import os
import sys
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

def create_weekly_file(weekly_notes_folder_path):
    # Calculate the nearest upcoming Sunday
    today = datetime.now()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:  # If today is Sunday, set days_until_sunday to 7 to get the next Sunday
        days_until_sunday = 7
    upcoming_sunday = today + timedelta(days=days_until_sunday)
    
    # Calculate the preceding Monday (6 days before Sunday)
    preceding_monday = upcoming_sunday - timedelta(days=6)
    
    # Format dates
    formatted_sunday = upcoming_sunday.strftime("%Y-%m-%d")
    formatted_monday = preceding_monday.strftime("%Y-%m-%d")
    
    # Create the file name
    file_name = f"Week-Ending-{formatted_sunday}.md"
    dropbox_file_path = f"{weekly_notes_folder_path}/{file_name}"
    
    # Create file content with date range and dataview queries
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
OR outgoing([[{upcoming_sunday.strftime("%b %d, %Y")}]])
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
OR [[{upcoming_sunday.strftime("%b %d, %Y")}]]
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
OR outgoing([[{upcoming_sunday.strftime("%b %d, %Y")}]])
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
OR [[{upcoming_sunday.strftime("%b %d, %Y")}]]
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
OR outgoing([[{upcoming_sunday.strftime("%b %d, %Y")}]])
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
OR [[{upcoming_sunday.strftime("%b %d, %Y")}]]
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
OR outgoing([[{upcoming_sunday.strftime("%b %d, %Y")}]])
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
OR [[{upcoming_sunday.strftime("%b %d, %Y")}]]
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
OR outgoing([[{upcoming_sunday.strftime("%b %d, %Y")}]])
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
OR [[{upcoming_sunday.strftime("%b %d, %Y")}]]
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
OR outgoing([[{upcoming_sunday.strftime("%b %d, %Y")}]])
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
OR [[{upcoming_sunday.strftime("%b %d, %Y")}]]
WHERE contains(file.folder, "06_Notes+Ideas")
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
OR [[{upcoming_sunday.strftime("%b %d, %Y")}]]
SORT file.mtime DESC
```
"""
    
    # Check if the file already exists
    try:
        dbx.files_get_metadata(dropbox_file_path)
        print(f"File '{file_name}' already exists in Dropbox. Skipping creation.")
    except dropbox.exceptions.ApiError as e:
        if isinstance(e.error, dropbox.files.GetMetadataError):
            print(f"File '{file_name}' does not exist in Dropbox. Creating it now.")
            # Upload the file with content instead of empty file
            dbx.files_upload(file_content.encode('utf-8'), dropbox_file_path)
            print(f"Successfully created file '{file_name}' with content in Dropbox.")
        else:
            raise

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
        except dropbox.exceptions.ApiError as e:
            if isinstance(e.error, dropbox.files.GetMetadataError):
                raise FileNotFoundError("'_Weeks' subfolder not found")
            else:
                raise
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    create_weekly_file(weekly_notes_folder_path)

if __name__ == "__main__":
    main()
