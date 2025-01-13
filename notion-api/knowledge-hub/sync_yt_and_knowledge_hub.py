#!/usr/bin/env python3
import os
import re
import redis
import requests
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

# Define the path to the .env file relative to the script's location
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
# Load environment variables from the .env file
load_dotenv(dotenv_path=env_path)

# Redis connection
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Notion environment vars
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_KNOWLEDGE_HUB_DB = os.getenv('NOTION_KNOWLEDGE_HUB_DB')
notion_api_key = os.getenv('NOTION_API_KEY')          # kept for script continuity
notion_knowledge_hub_db = os.getenv('NOTION_KNOWLEDGE_HUB_DB')  # kept for script continuity

# YouTube Gmail environment var
youtube_saves_email_address = os.getenv('YOUTUBE_SAVES_EMAIL_ADDRESS')

# Basic checks
required_env_vars = [
    'NOTION_API_KEY', 'NOTION_KNOWLEDGE_HUB_DB', 'YOUTUBE_SAVES_EMAIL_ADDRESS'
]
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"{var} environment variable is not set.")

# Initialize Notion clients
notion = Client(auth=notion_api_key)                # For YouTube->Notion
notion_for_obsidian = Client(auth=NOTION_API_KEY)   # For Notion->Obsidian

# Obsidian Knowledge Hub path
OBSIDIAN_KNOWLEDGE_HUB_PATH = os.getenv('OBSIDIAN_KNOWLEDGE_HUB_PATH')
if not OBSIDIAN_KNOWLEDGE_HUB_PATH:
    raise ValueError("OBSIDIAN_KNOWLEDGE_HUB_PATH environment variable is not set.")

# Create output path if not exists
output_path = Path(OBSIDIAN_KNOWLEDGE_HUB_PATH)
output_path.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

###############################################################################
# REDIS TIMESTAMP (UNIFIED FOR BOTH FLOWS)
###############################################################################
def get_last_synced_knowledge_hub_at():
    """
    Retrieve the last synced timestamp from Redis for your Knowledge Hub 
    (used by both the YouTube->Notion and Notion->Obsidian flows).
    """
    last_checked = redis_client.get("last_synced_knowledge_hub_at")
    if last_checked:
        return datetime.strptime(last_checked, '%Y-%m-%dT%H:%M:%S%z')
    return None

def update_last_synced_knowledge_hub_at():
    """
    Update the last synced timestamp in Redis for your Knowledge Hub 
    (used by both flows).
    """
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z')
    redis_client.set("last_synced_knowledge_hub_at", now)
    print(f"Updated 'last_synced_knowledge_hub_at' in Redis to: {now}")

###############################################################################
# 1) YOUTUBE (GMAIL) -> NOTION
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
            "url": {
                "equals": url
            }
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
    print(f"Added to Notion: {title}")

def search_messages(service, user_id='me', last_checked_at=None):
    """Search for messages in Gmail."""
    try:
        query = f"from:{youtube_saves_email_address} subject:Watch"
        if last_checked_at:
            # Gmail uses 'YYYY/MM/DD' for after:
            query += f" after:{last_checked_at.strftime('%Y/%m/%d')}"

        print(f"Using Gmail query: {query}")

        youtube_shares = []
        results = service.users().messages().list(
            userId=user_id,
            q=query
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            print("No messages found matching the query.")
            return []

        print(f"Found {len(messages)} messages matching the query.")

        for message in messages:
            msg = service.users().messages().get(userId=user_id, id=message['id']).execute()

            msg_date = datetime.fromtimestamp(int(msg['internalDate']) / 1000, tz=timezone.utc)
            print(f"Processing message dated: {msg_date}")

            payload = msg['payload']
            headers = payload['headers']

            # Extract the subject
            subject = next(header['value'] for header in headers if header['name'] == 'Subject')
            print(f"Email subject: {subject}")

            # Clean the subject
            clean_title = clean_subject(subject)
            print(f"Cleaned title: {clean_title}")

            url = extract_url(msg['snippet'])
            if not url:
                print(f"Skipping email: No URL found in snippet. Subject: {subject}")
                continue

            if check_existing_entry(url):
                print(f"Skipping email: URL already exists in Notion. Subject: {subject}, URL: {url}")
                continue

            youtube_shares.append({'title': clean_title, 'url': url})
            print(f"Prepared for addition: Title: {clean_title}, URL: {url}")

        print(f"Total emails processed: {len(messages)}")
        print(f"New YouTube shares found: {len(youtube_shares)}")
        return youtube_shares

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def youtube_to_notion_main():
    """Main entry point for the YouTube->Notion flow."""
    try:
        print("Initializing Gmail service...")
        service = get_gmail_service()

        last_checked_at = get_last_synced_knowledge_hub_at()
        if last_checked_at:
            print(f"Searching for YouTube share emails since {last_checked_at}...")
        else:
            print("No previous check timestamp found in Redis. Searching all emails...")

        youtube_shares = search_messages(service, last_checked_at=last_checked_at)

        if youtube_shares:
            print(f"Found {len(youtube_shares)} new YouTube share emails:")
            for share in youtube_shares:
                add_to_notion(share['title'], share['url'])
        else:
            print('No new YouTube share emails found.')

        update_last_synced_knowledge_hub_at()
    except Exception as e:
        print(f"An error occurred: {e}")

###############################################################################
# 2) NOTION -> OBSIDIAN
###############################################################################
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

            # Recursively parse children if has_children
            if block.get("has_children"):
                markdown_content += fetch_and_parse_blocks(block["id"], headers)

        return markdown_content
    except Exception as e:
        logger.error(f"Error parsing blocks for block ID {block_id}: {e}")
        return ""

def parse_paragraph(block):
    text = extract_text_notion(block["paragraph"]["rich_text"])
    return f"{text}\n\n"

def parse_heading(block, block_type):
    text = extract_text_notion(block[block_type]["rich_text"])
    level = block_type.split("_")[-1]
    return f"{'#' * int(level)} {text}\n\n"

def parse_image(block):
    image_url = block["image"].get("file", {}).get("url", block["image"].get("external", {}).get("url", ""))
    return f"![Image]({image_url})\n\n"

def parse_list_item(block, prefix, indent_level):
    text = extract_text_notion(block[block["type"]]["rich_text"])
    indent = "  " * indent_level
    return f"{indent}{prefix}{text}\n"

def parse_to_do(block):
    checked = block["to_do"]["checked"]
    text = extract_text_notion(block["to_do"]["rich_text"])
    checkbox = "[x]" if checked else "[ ]"
    return f"- {checkbox} {text}\n"

def parse_quote(block):
    text = extract_text_notion(block["quote"]["rich_text"])
    return f"> {text}\n\n"

def parse_code(block):
    code = block["code"]["rich_text"][0]["text"]["content"]
    language = block["code"].get("language", "")
    return f"```{language}\n{code}\n```\n\n"

def parse_callout(block):
    icon = block["callout"].get("icon", {}).get("emoji", "")
    text = extract_text_notion(block["callout"]["rich_text"])
    return f"> {icon} {text}\n\n"

def parse_toggle(block):
    text = extract_text_notion(block["toggle"]["rich_text"])
    toggle_content = f"* {text}\n"
    if block.get("has_children"):
        toggle_content += fetch_and_parse_blocks(block["id"], headers)
    return toggle_content

def extract_text_notion(rich_text_array):
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

def notion_to_obsidian_main():
    """
    Main entry point for the Notion->Obsidian flow,
    using the same Redis-based last synced timestamp as YouTube->Notion.
    """
    logger.info("Starting Notion to Obsidian sync script.")

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    # Use the unified Redis-based timestamp
    last_run_timestamp = get_last_synced_knowledge_hub_at()
    if not last_run_timestamp:
        # If we've never synced, default to something like 1 day ago
        last_run_timestamp = datetime.now(timezone.utc) - timedelta(days=1)

    logger.info(f"Processing pages created after: {last_run_timestamp}")

    skipped_files_due_to_existence = []
    skipped_files_due_to_error = []

    try:
        pages = notion_for_obsidian.databases.query(
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
        filename = None
        try:
            title = page['properties']['Name']['title'][0]['plain_text']
            url = page['properties'].get('URL', {}).get('url', '')

            content = fetch_and_parse_blocks(page['id'], headers)

            created_time = datetime.fromisoformat(page['created_time'].rstrip('Z'))
            # On Windows, strftime('%-d') can be replaced with '%#d' or removed.  
            # Here we keep '%-d' as is, but be mindful if you're on Windows.
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
URL: {url}
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
            if filename:
                skipped_files_due_to_error.append(filename)
            continue

    logger.info(f"Total pages processed: {pages_processed}")
    
    # Log files skipped
    if skipped_files_due_to_existence:
        logger.info(f"Files skipped (already exist): {', '.join(skipped_files_due_to_existence)}")
    if skipped_files_due_to_error:
        logger.info(f"Files skipped (errors): {', '.join(skipped_files_due_to_error)}")

    # Update the unified timestamp after finishing
    update_last_synced_knowledge_hub_at()

# MASTER MAIN
def main():
    """
    Master entry point that calls:
      1) youtube_to_notion_main() - fetch YouTube links from Gmail, store in Notion
      2) notion_to_obsidian_main() - fetch from Notion, export to Obsidian

    Both use the same Redis-based 'last_synced_knowledge_hub_at'.
    """
    youtube_to_notion_main()
    notion_to_obsidian_main()

if __name__ == '__main__':
    main()

