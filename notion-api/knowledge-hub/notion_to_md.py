import os
import requests
import re
from dotenv import load_dotenv
from pathlib import Path
from notion_client import Client
from datetime import datetime, timezone, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import logging

# Define the path to the .env file relative to the script's location
env_path = Path(__file__).resolve().parent.parent.parent / '.env'

# Load environment variables from the .env file
load_dotenv(dotenv_path=env_path)

# Notion setup
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_KNOWLEDGE_HUB_DB = os.getenv('NOTION_KNOWLEDGE_HUB_DB')

# Google Sheets setup
GDRIVE_CREDENTIALS_PATH = os.getenv('GDRIVE_CREDENTIALS_PATH')
GOOGLE_SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Obsidian Knowledge Hub path
OBSIDIAN_KNOWLEDGE_HUB_PATH = os.getenv('OBSIDIAN_KNOWLEDGE_HUB_PATH')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Ensure all required environment variables are set
required_env_vars = [
    'NOTION_API_KEY', 'NOTION_KNOWLEDGE_HUB_DB', 'GDRIVE_CREDENTIALS_PATH',
    'GOOGLE_SPREADSHEET_ID', 'GOOGLE_SHEET_NAME', 'OBSIDIAN_KNOWLEDGE_HUB_PATH'
]
for var in required_env_vars:
    if not os.getenv(var):
        logger.error(f"{var} environment variable is not set.")
        raise ValueError(f"{var} environment variable is not set.")

# Initialize Notion client
notion = Client(auth=NOTION_API_KEY)

# Ensure the output path exists
output_path = Path(OBSIDIAN_KNOWLEDGE_HUB_PATH) if OBSIDIAN_KNOWLEDGE_HUB_PATH else Path('output')
output_path.mkdir(parents=True, exist_ok=True)

# Google Sheets functions
def get_sheets_service():
    creds = Credentials.from_service_account_file(GDRIVE_CREDENTIALS_PATH, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def get_last_run_timestamp():
    logger.info("Fetching last run timestamp from Google Sheets.")
    service = get_sheets_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range=f'{GOOGLE_SHEET_NAME}!A:A'
    ).execute()
    values = result.get('values', [])
    if not values:
        logger.warning("No timestamps found in Google Sheets. Defaulting to 24 hours ago.")
        return None
    last_timestamp = values[-1][0]
    return datetime.strptime(last_timestamp, '%m/%d/%Y %H:%M:%S').replace(tzinfo=timezone.utc)

def update_run_timestamp():
    logger.info("Updating run timestamp in Google Sheets.")
    service = get_sheets_service()
    now = datetime.now(timezone.utc).strftime('%m/%d/%Y %H:%M:%S')
    service.spreadsheets().values().append(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range=f'{GOOGLE_SHEET_NAME}!A:A',
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
        body={'values': [[now]]}
    ).execute()
    logger.info(f"Timestamp updated: {now}")

# Notion parsing functions
def fetch_and_parse_blocks(block_id, headers):
    try:
        blocks_url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        response = requests.get(blocks_url, headers=headers)
        response.raise_for_status()
        data_blocks = response.json()

        markdown_content = ""
        for block in data_blocks["results"]:
            block_type = block["type"]

            if block_type == "paragraph":
                markdown_content += parse_paragraph(block)
            elif block_type.startswith("heading_"):
                markdown_content += parse_heading(block, block_type)
            elif block_type == "bulleted_list_item":
                markdown_content += parse_list_item(block, "- ", 0)
            elif block_type == "numbered_list_item":
                markdown_content += parse_list_item(block, "1. ", 0)
            elif block_type == "to_do":
                markdown_content += parse_to_do(block)
            elif block_type == "quote":
                markdown_content += parse_quote(block)
            elif block_type == "code":
                markdown_content += parse_code(block)
            elif block_type == "divider":
                markdown_content += "---\n"
            elif block_type == "image":
                markdown_content += parse_image(block)
            elif block_type == "callout":
                markdown_content += parse_callout(block)
            elif block_type == "toggle":
                markdown_content += parse_toggle(block)

            if block.get("has_children"):
                markdown_content += fetch_and_parse_blocks(block["id"], headers)

        return markdown_content
    except Exception as e:
        logger.error(f"Error parsing blocks for block ID {block_id}: {e}")
        return ""

def parse_paragraph(block):
    text = extract_text(block["paragraph"]["rich_text"])
    return f"{text}\n\n"

def parse_heading(block, block_type):
    text = extract_text(block[block_type]["rich_text"])
    level = block_type.split("_")[-1]
    return f"{'#' * int(level)} {text}\n\n"

def parse_image(block):
    image_url = block["image"].get("file", {}).get("url", block["image"].get("external", {}).get("url", ""))
    return f"![Image]({image_url})\n\n"

def parse_list_item(block, prefix, indent_level):
    text = extract_text(block[block["type"]]["rich_text"])
    indent = "  " * indent_level
    return f"{indent}{prefix}{text}\n"

def parse_to_do(block):
    checked = block["to_do"]["checked"]
    text = extract_text(block["to_do"]["rich_text"])
    checkbox = "[x]" if checked else "[ ]"
    return f"- {checkbox} {text}\n"

def parse_quote(block):
    text = extract_text(block["quote"]["rich_text"])
    return f"> {text}\n\n"

def parse_code(block):
    code = block["code"]["rich_text"][0]["text"]["content"]
    language = block["code"].get("language", "")
    return f"```{language}\n{code}\n```\n\n"

def parse_callout(block):
    icon = block["callout"].get("icon", {}).get("emoji", "")
    text = extract_text(block["callout"]["rich_text"])
    return f"> {icon} {text}\n\n"

def parse_toggle(block):
    text = extract_text(block["toggle"]["rich_text"])
    toggle_content = f"* {text}\n"
    if block.get("has_children"):
        toggle_content += fetch_and_parse_blocks(block["id"], headers)
    return toggle_content

def extract_text(rich_text_array):
    text = ""
    for rich_text in rich_text_array:
        if 'text' in rich_text:
            plain_text = rich_text["text"]["content"]
            annotations = rich_text["annotations"]
            if annotations.get("bold"):
                plain_text = f"**{plain_text}**"
            if annotations.get("italic"):
                plain_text = f"*{plain_text}*"
            if annotations.get("strikethrough"):
                plain_text = f"~~{plain_text}~~"
            if annotations.get("underline"):
                plain_text = f"<u>{plain_text}</u>"
            if annotations.get("code"):
                plain_text = f"`{plain_text}`"
            if rich_text["text"].get("link"):
                url = rich_text["text"]["link"]["url"]
                plain_text = f"[{plain_text}]({url})"
            text += plain_text
    return text

def sanitize_filename(title):
    return re.sub(r'[\/:*?"<>|]', '_', title)

# Main execution
def main():
    logger.info("Starting Notion to Obsidian sync script.")
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    last_run_timestamp = get_last_run_timestamp()
    if not last_run_timestamp:
        last_run_timestamp = datetime.now(timezone.utc) - timedelta(days=1)

    logger.info(f"Processing pages created after: {last_run_timestamp}")

    skipped_files_due_to_existence = []
    skipped_files_due_to_error = []

    try:
        pages = notion.databases.query(
            **{
                "database_id": NOTION_KNOWLEDGE_HUB_DB,
                "filter": {
                    "property": "Created",
                    "date": {
                        "after": last_run_timestamp.isoformat()
                    }
                },
                "sorts": [
                    {
                        "property": "Created",
                        "direction": "ascending"
                    },
                ],
            }
        )["results"]
        logger.info(f"Total pages identified for migration: {len(pages)}")
    except Exception as e:
        logger.error(f"Failed to query Notion database: {e}")
        return

    pages_processed = 0
    for page in pages:
        try:
            title = page['properties']['Name']['title'][0]['plain_text']
            url = page['properties']['URL']['url'] if 'URL' in page['properties'] else None
            content = fetch_and_parse_blocks(page['id'], headers)
            
            created_time = datetime.fromisoformat(page['created_time'].rstrip('Z'))
            formatted_date = created_time.strftime("%b %-d, %Y")
            
            filename = sanitize_filename(title) + '.md'
            full_path = output_path / filename

            if full_path.exists():
                logger.warning(f"File '{filename}' already exists. Skipping.")
                skipped_files_due_to_existence.append(filename)
                continue

            markdown_content = f"""---
Journal: 
  - "[[{formatted_date}]]"
created time: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f%z')}
modified time: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f%z')}
key words: 
People: 
URL: {url if url else ''}
Notes+Ideas: 
Experiences: 
Tags: 
---

## {title}

"""
            markdown_content += content

            with open(full_path, 'w', encoding='utf-8') as md_file:
                md_file.write(markdown_content)

            logger.info(f"Markdown file created: {full_path}")
            pages_processed += 1

        except Exception as e:
            logger.error(f"Error processing page {page['id']} ({title}): {e}")
            skipped_files_due_to_error.append(filename)
            continue

    logger.info(f"Total pages processed: {pages_processed}")
    
    # Log files skipped due to existence
    if skipped_files_due_to_existence:
        logger.info(f"Files skipped due to existence: {', '.join(skipped_files_due_to_existence)}")

    # Log files skipped due to errors
    if skipped_files_due_to_error:
        logger.info(f"Files skipped due to errors: {', '.join(skipped_files_due_to_error)}")

    update_run_timestamp()

if __name__ == "__main__":
    main()

