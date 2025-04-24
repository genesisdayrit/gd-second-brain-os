import os
import dropbox
import redis
import requests
import re
from notion_client import Client
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path
import logging
import pytz

# Define the path to the .env file relative to the script's location
env_path = Path(__file__).resolve().parent.parent.parent / '.env'

# Load environment variables
load_dotenv(dotenv_path=env_path)

# --- Timezone Configuration ---
# Note: We'll still use UTC for timestamp storage for consistency with APIs and databases
timezone_str = os.getenv("SYSTEM_TIMEZONE", "US/Eastern")
system_tz = pytz.timezone(timezone_str)

# Redis configuration
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.StrictRedis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)
REDIS_LAST_RUN_KEY = "notion_knowledge_hub_last_run_at"

# Retrieve Dropbox access token from Redis
def get_dropbox_access_token():
    """Retrieve Dropbox access token from Redis."""
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Dropbox Client Initialization
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# Notion API configuration
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_KNOWLEDGE_HUB_DB = os.getenv('NOTION_KNOWLEDGE_HUB_DB')

# Dropbox Obsidian Vault path
DROPBOX_OBSIDIAN_VAULT_PATH = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.info(f"Using system timezone: {timezone_str}")
logger.info(f"Using UTC for timestamp storage for API and database consistency")

# Initialize Notion client
notion = Client(auth=NOTION_API_KEY)

# Function to search for the _Knowledge-Hub folder in the Dropbox Obsidian Vault
def find_knowledge_hub_path(vault_path):
    """Search for the `_Knowledge-Hub` folder in the Dropbox Obsidian Vault path."""
    try:
        response = dbx.files_list_folder(vault_path)
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Knowledge-Hub"):
                logger.info(f"Found Knowledge Hub path: {entry.path_lower}")
                return entry.path_lower
        raise FileNotFoundError("Could not find a folder ending with '_Knowledge-Hub' in the specified vault path.")
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Dropbox API error while searching for _Knowledge-Hub: {e}")
        raise e

# Retrieve the last run timestamp from Redis or default to 24 hours ago
def get_last_run_timestamp():
    try:
        last_run = r.get(REDIS_LAST_RUN_KEY)
        if last_run:
            return datetime.fromisoformat(last_run).replace(tzinfo=timezone.utc)
        else:
            default_time = datetime.now(timezone.utc) - timedelta(days=1)
            logger.info(f"No last run timestamp found in Redis. Defaulting to: {default_time}")
            return default_time
    except Exception as e:
        logger.error(f"Error retrieving last run timestamp: {e}")
        return datetime.now(timezone.utc) - timedelta(days=1)

# Update the last run timestamp in Redis
def update_run_timestamp():
    """Update the last run timestamp in Redis using UTC for consistency with APIs."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        r.set(REDIS_LAST_RUN_KEY, now)
        logger.info(f"Updated last run timestamp in Redis: {now}")
    except Exception as e:
        logger.error(f"Error updating last run timestamp: {e}")

# Parse Notion block content into Markdown
def fetch_and_parse_blocks(block_id, headers):
    try:
        blocks_url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        response = requests.get(blocks_url, headers=headers)
        response.raise_for_status()
        data_blocks = response.json()

        markdown_content = ""
        for block in data_blocks["results"]:
            block_type = block["type"]
            markdown_content += parse_block(block, block_type, headers)

        return markdown_content
    except Exception as e:
        logger.error(f"Error parsing blocks for block ID {block_id}: {e}")
        return ""

def parse_block(block, block_type, headers):
    try:
        if block_type == "paragraph":
            return parse_paragraph(block)
        elif block_type.startswith("heading_"):
            return parse_heading(block, block_type)
        elif block_type == "bulleted_list_item":
            return parse_list_item(block, "- ", 0)
        elif block_type == "numbered_list_item":
            return parse_list_item(block, "1. ", 0)
        elif block_type == "to_do":
            return parse_to_do(block)
        elif block_type == "quote":
            return parse_quote(block)
        elif block_type == "code":
            return parse_code(block)
        elif block_type == "divider":
            return "---\n"
        elif block_type == "image":
            return parse_image(block)
        elif block_type == "callout":
            return parse_callout(block)
        elif block_type == "toggle":
            return parse_toggle(block, headers)
        return ""
    except Exception as e:
        logger.error(f"Error parsing block type {block_type}: {e}")
        return ""

# Sanitize filenames for valid OS usage
def sanitize_filename(title):
    return re.sub(r'[\/:*?"<>|]', '_', title)

def parse_paragraph(block):
    return f"{extract_text(block['paragraph']['rich_text'])}\n\n"

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
    checkbox = "[x]" if block["to_do"]["checked"] else "[ ]"
    text = extract_text(block["to_do"]["rich_text"])
    return f"- {checkbox} {text}\n"

def parse_quote(block):
    return f"> {extract_text(block['quote']['rich_text'])}\n\n"

def parse_code(block):
    code = block["code"]["rich_text"][0]["text"]["content"]
    language = block["code"].get("language", "")
    return f"```{language}\n{code}\n```\n\n"

def parse_callout(block):
    icon = block["callout"].get("icon", {}).get("emoji", "")
    text = extract_text(block["callout"]["rich_text"])
    return f"> {icon} {text}\n\n"

def parse_toggle(block, headers):
    text = extract_text(block["toggle"]["rich_text"])
    toggle_content = f"* {text}\n"
    if block.get("has_children"):
        toggle_content += fetch_and_parse_blocks(block["id"], headers)
    return toggle_content

def extract_text(rich_text_array):
    text = ""
    for rich_text in rich_text_array:
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

# Process Notion pages
def process_notion_pages(knowledge_hub_path):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    last_run_timestamp = get_last_run_timestamp()
    logger.info(f"Processing pages created after: {last_run_timestamp}")

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
                "sorts": [{"property": "Created", "direction": "ascending"}],
            }
        )["results"]
        logger.info(f"Total pages identified for processing: {len(pages)}")
    except Exception as e:
        logger.error(f"Failed to query Notion database: {e}")
        return

    for page in pages:
        try:
            title = page['properties']['Name']['title'][0]['plain_text']
            url = page['properties'].get('URL', {}).get('url', '')
            content = fetch_and_parse_blocks(page['id'], headers)
            filename = sanitize_filename(title) + '.md'
            dropbox_file_path = f"{knowledge_hub_path}/{filename}"

            # Check if file already exists in Dropbox
            try:
                dbx.files_get_metadata(dropbox_file_path)
                logger.warning(f"File '{filename}' already exists in Dropbox. Skipping.")
                continue
            except dropbox.exceptions.ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    pass  # File does not exist; proceed to upload
                else:
                    raise e

            # Get the current date in user's local timezone for the journal link
            now_local = datetime.now(timezone.utc).astimezone(system_tz)
            formatted_local_date = now_local.strftime('%b %-d, %Y')

            # Continue using UTC for timestamps in metadata for consistency
            now_utc = datetime.now(timezone.utc)

            # Construct Markdown content
            markdown_content = f"""---
Journal: 
  - "[[{formatted_local_date}]]"
created time: {now_utc.isoformat()}
modified time: {now_utc.isoformat()}
key words: 
People: 
URL: {url if url else ''}
Notes+Ideas: 
Experiences: 
Tags: 
---

## {title}

{content}
"""
            # Upload file to Dropbox
            dbx.files_upload(
                markdown_content.encode('utf-8'),
                dropbox_file_path,
                mode=dropbox.files.WriteMode.overwrite
            )
            logger.info(f"Markdown file uploaded to Dropbox: {dropbox_file_path}")
        except Exception as e:
            logger.error(f"Error processing page {page.get('id')}: {e}")

    update_run_timestamp()

# Main function
def main():
    if not NOTION_API_KEY or not NOTION_KNOWLEDGE_HUB_DB:
        logger.error("Error: Missing required environment variables for Notion API.")
        return

    if not DROPBOX_OBSIDIAN_VAULT_PATH:
        logger.error("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set.")
        return

    try:
        knowledge_hub_path = find_knowledge_hub_path(DROPBOX_OBSIDIAN_VAULT_PATH)
        process_notion_pages(knowledge_hub_path)
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
