import json
import os
import re
import shutil
from dotenv import load_dotenv
from pathlib import Path

# Define the path to the .env file relative to the script's location
env_path = Path(__file__).resolve().parent.parent / '.env'

# Load environment variables from the .env file
load_dotenv(dotenv_path=env_path)

# Ask for the database name/subfolder name
database_name = input("Please enter the database name or subfolder name: ")

# Construct the base path within the 'database-extractions' subfolder
base_path = Path('database-extractions') / database_name

# Construct the destination path within the 'md-files' subfolder
destination_path = base_path / 'md-files'

# Ensure the destination path is clean
if destination_path.exists():
    shutil.rmtree(destination_path)  # Remove the existing directory and its contents

destination_path.mkdir(parents=True, exist_ok=True)  # Recreate the directory

# Function to get the latest JSON file based on timestamp within the database name subfolder
def get_latest_json_file():
    json_files = [f for f in os.listdir(base_path) if f.startswith('extracted_content_') and f.endswith('.json')]
    if not json_files:
        raise FileNotFoundError(f"No extracted content JSON files found in {base_path}.")
    json_files.sort(reverse=True)
    return base_path / json_files[0]

# Load JSON data from the latest file within the specified database name subfolder
json_file_path = get_latest_json_file()
with open(json_file_path, 'r') as f:
    data = json.load(f)

# Function to sanitize the title for use as a filename
def sanitize_filename(title):
    return re.sub(r'[\/:*?"<>|]', '_', title)

# Function to create a Markdown file from JSON data
def create_markdown_files(data):
    for entry in data:
        title = entry['title']
        url = entry['url']
        content = entry.get('content', '')

        # Generate a sanitized filename
        filename = sanitize_filename(title) + '.md'
        full_path = destination_path / filename

        # Prepare the Markdown content
        markdown_content = f"# {title}\n\n"
        markdown_content += f"Source: {url}\n\n"
        markdown_content += f"{content}\n"

        # Save the Markdown content to a file
        with open(full_path, 'w') as md_file:
            md_file.write(markdown_content)
        
        print(f"Markdown file created: {full_path}")

# Create Markdown files from the JSON data
create_markdown_files(data)
