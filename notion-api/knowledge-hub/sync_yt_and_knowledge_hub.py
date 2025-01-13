#!/usr/bin/env python3
import os
import re
import redis
import requests
import dropbox
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials


env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


# REDIS SETUP
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)
redis_client = redis.StrictRedis(
    host=redis_host, port=redis_port, password=redis_password, decode_responses=True
)

# Redis Last Synced Key
LAST_SYNCED_KEY = "last_synced_knowledge_hub_at"

# NOTION SETUP
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_KNOWLEDGE_HUB_DB = os.getenv('NOTION_KNOWLEDGE_HUB_DB')
if not NOTION_API_KEY or not NOTION_KNOWLEDGE_HUB_DB:
    raise ValueError("NOTION_API_KEY and NOTION_KNOWLEDGE_HUB_DB must be set in .env.")

# For continuity with older variable names (from your code samples):
notion_api_key = NOTION_API_KEY
notion_knowledge_hub_db = NOTION_KNOWLEDGE_HUB_DB

# Initialize Notion client(s)
notion = Client(auth=notion_api_key)  # for YouTube->Notion
notion_for_dropbox = Client(auth=NOTION_API_KEY)  # for Notion->Dropbox

# YOUTUBE GMAIL ENV VAR
youtube_saves_email_address = os.getenv('YOUTUBE_SAVES_EMAIL_ADDRESS')
if not youtube_saves_email_address:
    raise ValueError("YOUTUBE_SAVES_EMAIL_ADDRESS must be set in .env.")

# DROPBOX SETUP
DROPBOX_OBSIDIAN_VAULT_PATH = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
if not DROPBOX_OBSIDIAN_VAULT_PATH:
    raise ValueError("DROPBOX_OBSIDIAN_VAULT_PATH must be set in .env.")

# Retrieve Dropbox access token from Redis (as per your example)
def get_dropbox_access_token():
    """Retrieve Dropbox access token from Redis."""
    access_token = redis_client.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# LOGGING
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# SHARED REDIS TIMESTAMP FUNCTIONS
def get_last_synced_knowledge_hub_at():
    """Retrieve the last synced timestamp from Redis for your Knowledge Hub."""
    last_checked = redis_client.get(LAST_SYNCED_KEY)
    if last_checked:
        return datetime.strptime(last_checked, '%Y-%m-%dT%H:%M:%S%z')
    return None

def update_last_synced_knowledge_hub_at():
    """Update the last synced timestamp in Redis for your Knowledge Hub."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z')
    redis_client.set(LAST_SYNCED_KEY, now)
    logger.info(f"Updated '{LAST_SYNCED_KEY}' in Redis to: {now}")

###############################################################################
# 1) YOUTUBE (GMAIL) → NOTION
###############################################################################
SCOPES_GMAIL = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """Retrieve Gmail API service using Redis-stored access token."""
    access_token = redis_client.get("gmail_access_token")
    if not access_token:
        raise ValueError("No access token found in Redis. Ensure tokens are set up and refreshed properly.")

    creds = Credentials(
        token=access_token,
        refresh_token=None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=None,
        client_secret=None,
    )

    if creds.expired:
        raise ValueError("Access token expired. Run the token refresh process to update Redis.")

    return build('gmail', 'v1', credentials=creds)

def clean_subject(subject):
    """Clean the email subject line."""
    return re.sub(r'^Watch "(.+)" on YouTube$', r'\1', subject)

def extract_url(snippet):
    """Extract a URL from the email snippet."""
    url_match = re.search(r'(https?://\S+)', snippet)
    return url_match.group(1) if url_match else None

def check_existing_entry(url):
    """Check if the URL already exists in the Notion database."""
    results = notion.databases.query(
        database_id=notion_knowledge_hub_db,
        filter={
            "property": "URL",
            "url": {"equals": url}
        }
    ).get("results")
    return len(results) > 0

def add_to_notion(title, url):
    """Add a new entry to the Notion database."""
    notion.pages.create(
        parent={"database_id": notion_knowledge_hub_db},
        properties={
            "Name": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url}
        }
    )
    logger.info(f"Added to Notion: {title}")

def search_messages(service, user_id='me', last_checked_at=None):
    """Search for messages in Gmail containing YouTube share links."""
    try:
        query = f"from:{youtube_saves_email_address} subject:Watch"
        if last_checked_at:
            # Gmail uses YYYY/MM/DD for after
            query += f" after:{last_checked_at.strftime('%Y/%m/%d')}"

        logger.info(f"Using Gmail query: {query}")

        youtube_shares = []
        results = service.users().messages().list(userId=user_id, q=query).execute()

        messages = results.get('messages', [])
        if not messages:
            logger.info("No messages found matching the query.")
            return []

        logger.info(f"Found {len(messages)} messages matching the query.")

        for message in messages:
            msg = service.users().messages().get(userId=user_id, id=message['id']).execute()
            msg_date = datetime.fromtimestamp(int(msg['internalDate']) / 1000, tz=timezone.utc)

            payload = msg['payload']
            headers = payload['headers']

            # Extract the subject
            subject = next(header['value'] for header in headers if header['name'] == 'Subject')
            clean_title = clean_subject(subject)

            url = extract_url(msg['snippet'])
            if not url:
                logger.info(f"Skipping email: No URL found in snippet. Subject: {subject}")
                continue

            if check_existing_entry(url):
                logger.info(f"Skipping email: URL already exists in Notion. Subject: {subject}, URL: {url}")
                continue

            youtube_shares.append({'title': clean_title, 'url': url})
            logger.info(f"Prepared for addition: Title: {clean_title}, URL: {url}")

        logger.info(f"Total emails processed: {len(messages)}")
        logger.info(f"New YouTube shares found: {len(youtube_shares)}")
        return youtube_shares

    except HttpError as error:
        logger.error(f'An error occurred with Gmail API: {error}')
        return []

def youtube_to_notion_main():
    """Main entry point for the YouTube->Notion flow."""
    try:
        logger.info("Initializing Gmail service...")
        service = get_gmail_service()

        last_checked_at = get_last_synced_knowledge_hub_at()
        if last_checked_at:
            logger.info(f"Searching for YouTube share emails since {last_checked_at}...")
        else:
            logger.info("No previous check timestamp found in Redis. Searching all emails...")

        youtube_shares = search_messages(service, last_checked_at=last_checked_at)

        if youtube_shares:
            logger.info(f"Found {len(youtube_shares)} new YouTube share emails.")
            for share in youtube_shares:
                add_to_notion(share['title'], share['url'])
        else:
            logger.info("No new YouTube share emails found.")

        update_last_synced_knowledge_hub_at()
    except Exception as e:
        logger.error(f"An error occurred: {e}")

###############################################################################
# 2) NOTION → DROPBOX  (Replacing local Obsidian path with Dropbox approach)
###############################################################################
def find_knowledge_hub_path(vault_path):
    """
    Search for the `_Knowledge-Hub` folder in the Dropbox Obsidian Vault path.
    Returns the path_lower of the matched folder in Dropbox.
    """
    try:
        response = dbx.files_list_folder(vault_path)
        for entry in response.entries:
            if (isinstance(entry, dropbox.files.FolderMetadata) 
                and entry.name.endswith("_Knowledge-Hub")):
                logger.info(f"Found Knowledge Hub path in Dropbox: {entry.path_lower}")
                return entry.path_lower
        raise FileNotFoundError(
            "Could not find a folder ending with '_Knowledge-Hub' in the specified vault path."
        )
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Dropbox API error while searching for _Knowledge-Hub: {e}")
        raise e

def get_last_run_timestamp_dropbox():
    """
    Optionally: If you want a separate key for Notion->Dropbox, you could do so, 
    but we’re reusing get_last_synced_knowledge_hub_at() for both flows.
    This function is left here if needed. Otherwise, ignore or remove it.
    """
    return get_last_synced_knowledge_hub_at()

def update_run_timestamp_dropbox():
    """
    Optionally: If you want a separate key for Notion->Dropbox, you could do so, 
    but we’re reusing update_last_synced_knowledge_hub_at() for both flows.
    This function is left here if needed. Otherwise, ignore or remove it.
    """
    update_last_synced_knowledge_hub_at()

def fetch_and_parse_blocks_dropbox(block_id, headers):
    """
    Same as your other notion->md logic, but 
    named separately to avoid collisions if desired.
    """
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
    """
    For Dropbox flow, break out your existing parse logic. 
    This is the same approach you had in your original code.
    """
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

def parse_paragraph(block):
    return f"{extract_text(block['paragraph']['rich_text'])}\n\n"

def parse_heading(block, block_type):
    text = extract_text(block[block_type]["rich_text"])
    level = block_type.split("_")[-1]
    return f"{'#' * int(level)} {text}\n\n"

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

def parse_image(block):
    image_url = (
        block["image"].get("file", {}).get("url") or 
        block["image"].get("external", {}).get("url", "")
    )
    return f"![Image]({image_url})\n\n"

def parse_callout(block):
    icon = block["callout"].get("icon", {}).get("emoji", "")
    text = extract_text(block["callout"]["rich_text"])
    return f"> {icon} {text}\n\n"

def parse_toggle(block, headers):
    text = extract_text(block["toggle"]["rich_text"])
    toggle_content = f"* {text}\n"
    if block.get("has_children"):
        toggle_content += fetch_and_parse_blocks_dropbox(block["id"], headers)
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

def sanitize_filename(title):
    """Replace invalid filename chars with underscores."""
    return re.sub(r'[\/:*?"<>|]', '_', title)

def notion_to_dropbox_main():
    """
    Main entry point for the Notion->Dropbox flow, 
    using the same Redis-based last synced timestamp as YouTube->Notion.
    """
    logger.info("Starting Notion to Dropbox sync script.")

    # Attempt to find the `_Knowledge-Hub` folder in the Dropbox vault path
    try:
        knowledge_hub_path = find_knowledge_hub_path(DROPBOX_OBSIDIAN_VAULT_PATH)
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return
    except Exception as e:
        logger.error(f"An unexpected error occurred while searching for the _Knowledge-Hub folder: {e}")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    last_run_timestamp = get_last_synced_knowledge_hub_at()
    if not last_run_timestamp:
        last_run_timestamp = datetime.now(timezone.utc) - timedelta(days=1)

    logger.info(f"Processing Notion pages created after: {last_run_timestamp.isoformat()}")

    try:
        pages = notion_for_dropbox.databases.query(
            database_id=NOTION_KNOWLEDGE_HUB_DB,
            filter={
                "property": "Created",
                "date": {
                    "after": last_run_timestamp.isoformat()
                }
            },
            sorts=[{"property": "Created", "direction": "ascending"}]
        )["results"]
        logger.info(f"Total pages identified for processing: {len(pages)}")
    except Exception as e:
        logger.error(f"Failed to query Notion database: {e}")
        return

    for page in pages:
        try:
            title = page['properties']['Name']['title'][0]['plain_text']
            url = page['properties'].get('URL', {}).get('url', '')
            content = fetch_and_parse_blocks_dropbox(page['id'], headers)
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

            # Construct Markdown content
            created_time = datetime.fromisoformat(page['created_time'].rstrip('Z'))
            formatted_date = created_time.strftime("%b %-d, %Y")  # on Windows, may need to adjust
            now_str = datetime.now(timezone.utc).isoformat()

            markdown_content = f"""---
Journal: 
  - "[[{formatted_date}]]"
created time: {now_str}
modified time: {now_str}
key words: 
People: 
URL: {url}
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
            logger.error(f"Error processing Notion page {page.get('id')}: {e}")

    # Update unified Redis timestamp
    update_last_synced_knowledge_hub_at()

# MASTER MAIN
def main():
    """
    Master entry point that calls:
      1) youtube_to_notion_main() - fetch YouTube links from Gmail, store in Notion
      2) notion_to_dropbox_main() - fetch from Notion, export markdown to Dropbox

    Both use the same Redis-based 'last_synced_knowledge_hub_at'.
    """
    # 1) Pull YouTube share links into Notion
    youtube_to_notion_main()

    # 2) Export from Notion to Dropbox
    notion_to_dropbox_main()

if __name__ == '__main__':
    main()

