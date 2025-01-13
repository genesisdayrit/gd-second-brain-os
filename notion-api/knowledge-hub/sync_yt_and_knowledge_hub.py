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
import pytz

# ENV LOADING
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# REDIS SETUP
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)
redis_client = redis.StrictRedis(
    host=redis_host,
    port=redis_port,
    password=redis_password,
    decode_responses=True
)

# We use one key for the entire Knowledge Hub syncing process
LAST_SYNCED_KEY = "last_synced_knowledge_hub_at"

# NOTION SETUP
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_KNOWLEDGE_HUB_DB = os.getenv('NOTION_KNOWLEDGE_HUB_DB')
if not NOTION_API_KEY or not NOTION_KNOWLEDGE_HUB_DB:
    raise ValueError("NOTION_API_KEY and NOTION_KNOWLEDGE_HUB_DB must be set in .env.")

# For continuity with older variable names (from your code samples):
notion_api_key = NOTION_API_KEY
notion_knowledge_hub_db = NOTION_KNOWLEDGE_HUB_DB

# Initialize Notion clients
notion = Client(auth=notion_api_key)  
notion_for_dropbox = Client(auth=NOTION_API_KEY)  

# YOUTUBE (GMAIL) ENV VAR
youtube_saves_email_address = os.getenv('YOUTUBE_SAVES_EMAIL_ADDRESS')
if not youtube_saves_email_address:
    raise ValueError("YOUTUBE_SAVES_EMAIL_ADDRESS must be set in .env.")

# DROPBOX SETUP
DROPBOX_OBSIDIAN_VAULT_PATH = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
if not DROPBOX_OBSIDIAN_VAULT_PATH:
    raise ValueError("DROPBOX_OBSIDIAN_VAULT_PATH must be set in .env.")

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

# REDIS TIMESTAMP FUNCTIONS (Called only in main)
def get_last_synced_knowledge_hub_at():
    """
    Retrieve the last synced timestamp from Redis for your Knowledge Hub.
    If not set, we’ll default to something older in main().
    """
    last_checked = redis_client.get(LAST_SYNCED_KEY)
    if last_checked:
        return datetime.strptime(last_checked, '%Y-%m-%dT%H:%M:%S%z')
    return None

def update_last_synced_knowledge_hub_at():
    """
    Update the last synced timestamp in Redis for your Knowledge Hub.
    We'll only call this once at the end of main().
    """
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z')
    redis_client.set(LAST_SYNCED_KEY, now)
    logger.info(f"Updated '{LAST_SYNCED_KEY}' in Redis to: {now}")


# YOUTUBE (GMAIL) -> NOTION
SCOPES_GMAIL = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """
    Retrieve Gmail API service using the access token stored in Redis.
    (We do not update last_synced_knowledge_hub_at here.)
    """
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
    """Remove 'Watch \"...' pattern from subject to get a nicer title."""
    return re.sub(r'^Watch "(.+)" on YouTube$', r'\1', subject)

def extract_url(snippet):
    """Extract a single URL from the email snippet."""
    url_match = re.search(r'(https?://\S+)', snippet)
    return url_match.group(1) if url_match else None

def check_existing_entry(url):
    """Check if this URL is already in our Notion Knowledge Hub DB."""
    results = notion.databases.query(
        database_id=notion_knowledge_hub_db,
        filter={
            "property": "URL",
            "url": {"equals": url}
        }
    ).get("results")
    return len(results) > 0

def add_to_notion(title, url):
    """Add a new page to Notion with given title and URL."""
    notion.pages.create(
        parent={"database_id": notion_knowledge_hub_db},
        properties={
            "Name": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url}
        }
    )
    logger.info(f"Added to Notion: {title}")

def search_messages(service, last_checked_at=None):
    """
    Search for Gmail messages from youtube_saves_email_address 
    with subject:Watch, optionally since last_checked_at.
    """
    try:
        query = f"from:{youtube_saves_email_address} subject:Watch"
        if last_checked_at:
            query += f" after:{last_checked_at.strftime('%Y/%m/%d')}"

        logger.info(f"Gmail query: {query}")

        youtube_shares = []
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        if not messages:
            logger.info("No Gmail messages found for query.")
            return []

        logger.info(f"Found {len(messages)} candidate Gmail messages.")

        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            snippet = msg.get('snippet', '')

            # Extract subject
            headers = msg['payload']['headers']
            subject = next(h['value'] for h in headers if h['name'] == 'Subject')
            cleaned_title = clean_subject(subject)
            url = extract_url(snippet)

            if not url:
                logger.info(f"No URL found in snippet. Skipping. Subject: {subject}")
                continue

            if check_existing_entry(url):
                logger.info(f"URL already in Notion. Skipping. Subject: {subject}, URL: {url}")
                continue

            youtube_shares.append({'title': cleaned_title, 'url': url})
            logger.info(f"Prepared for Notion: {cleaned_title}")

        return youtube_shares

    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
        return []

def youtube_to_notion_main(last_checked_at):
    """
    Fetch YouTube share emails from Gmail (since last_checked_at) and insert them into Notion.
    We do NOT update the Redis timestamp here. We only do it once at the end of the entire process.
    """
    try:
        logger.info("Running YouTube -> Notion flow.")
        service = get_gmail_service()

        youtube_shares = search_messages(service, last_checked_at=last_checked_at)
        if youtube_shares:
            for share in youtube_shares:
                add_to_notion(share['title'], share['url'])
            logger.info(f"Inserted {len(youtube_shares)} new YouTube shares into Notion.")
        else:
            logger.info("No new YouTube shares to insert into Notion.")

    except Exception as e:
        logger.error(f"Error in YouTube->Notion flow: {e}")


# NOTION -> DROPBOX
def find_knowledge_hub_path(vault_path):
    """
    Look for a folder in Dropbox named *ending* with "_Knowledge-Hub" 
    within the given vault_path. Return its path_lower if found.
    """
    try:
        response = dbx.files_list_folder(vault_path)
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Knowledge-Hub"):
                logger.info(f"Found Dropbox Knowledge Hub path: {entry.path_lower}")
                return entry.path_lower
        raise FileNotFoundError(
            "No '_Knowledge-Hub' folder found in the specified Dropbox vault path."
        )
    except dropbox.exceptions.ApiError as e:
        logger.error(f"Dropbox error while searching for _Knowledge-Hub: {e}")
        raise

def fetch_and_parse_blocks_dropbox(block_id, headers):
    """
    Request and parse the child blocks of a Notion block, returning Markdown text.
    """
    try:
        blocks_url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        response = requests.get(blocks_url, headers=headers)
        response.raise_for_status()
        data_blocks = response.json()

        md_content = ""
        for block in data_blocks["results"]:
            btype = block["type"]
            md_content += parse_block(block, btype, headers)
        return md_content
    except Exception as e:
        logger.error(f"Error parsing Notion blocks (ID {block_id}): {e}")
        return ""

def parse_block(block, block_type, headers):
    """
    Dispatch function to parse individual block types into Markdown.
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
    txt = extract_text(block[block_type]["rich_text"])
    level = block_type.split("_")[-1]
    return f"{'#' * int(level)} {txt}\n\n"

def parse_list_item(block, prefix, indent_level):
    txt = extract_text(block[block["type"]]["rich_text"])
    indent = "  " * indent_level
    return f"{indent}{prefix}{txt}\n"

def parse_to_do(block):
    checkbox = "[x]" if block["to_do"]["checked"] else "[ ]"
    txt = extract_text(block["to_do"]["rich_text"])
    return f"- {checkbox} {txt}\n"

def parse_quote(block):
    return f"> {extract_text(block['quote']['rich_text'])}\n\n"

def parse_code(block):
    code = block["code"]["rich_text"][0]["text"]["content"]
    language = block["code"].get("language", "")
    return f"```{language}\n{code}\n```\n\n"

def parse_image(block):
    image_url = block["image"].get("file", {}).get("url") or block["image"].get("external", {}).get("url", "")
    return f"![Image]({image_url})\n\n"

def parse_callout(block):
    icon = block["callout"].get("icon", {}).get("emoji", "")
    txt = extract_text(block["callout"]["rich_text"])
    return f"> {icon} {txt}\n\n"

def parse_toggle(block, headers):
    txt = extract_text(block["toggle"]["rich_text"])
    toggle_content = f"* {txt}\n"
    if block.get("has_children"):
        toggle_content += fetch_and_parse_blocks_dropbox(block["id"], headers)
    return toggle_content

def extract_text(rich_text_array):
    text = ""
    for rtxt in rich_text_array:
        plain_text = rtxt["text"]["content"]
        ann = rtxt["annotations"]
        if ann.get("bold"):
            plain_text = f"**{plain_text}**"
        if ann.get("italic"):
            plain_text = f"*{plain_text}*"
        if ann.get("strikethrough"):
            plain_text = f"~~{plain_text}~~"
        if ann.get("underline"):
            plain_text = f"<u>{plain_text}</u>"
        if ann.get("code"):
            plain_text = f"`{plain_text}`"
        link_info = rtxt["text"].get("link")
        if link_info:
            url = link_info["url"]
            plain_text = f"[{plain_text}]({url})"
        text += plain_text
    return text

def sanitize_filename(title):
    """Replace invalid filename characters with underscores."""
    return re.sub(r'[\/:*?"<>|]', '_', title)

def notion_to_dropbox_main(last_checked_at):
    """
    Pull newly created Notion pages (after last_checked_at), convert them to Markdown,
    and upload to Dropbox under the _Knowledge-Hub folder. We do NOT update the Redis 
    timestamp here. We'll do it once at the very end of main().
    """
    logger.info("Running Notion -> Dropbox flow.")
    try:
        knowledge_hub_path = find_knowledge_hub_path(DROPBOX_OBSIDIAN_VAULT_PATH)
    except Exception as e:
        logger.error(f"Could not find Knowledge Hub path in Dropbox: {e}")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    if not last_checked_at:
        # If we've never synced, default to something older, e.g. 1 day
        last_checked_at = datetime.now(timezone.utc) - timedelta(days=1)

    logger.info(f"Fetching Notion pages created after: {last_checked_at.isoformat()}")

    try:
        pages = notion_for_dropbox.databases.query(
            database_id=NOTION_KNOWLEDGE_HUB_DB,
            filter={
                "property": "Created",
                "date": {
                    "after": last_checked_at.isoformat()
                }
            },
            sorts=[{"property": "Created", "direction": "ascending"}]
        )["results"]
        logger.info(f"Found {len(pages)} pages to process.")
    except Exception as e:
        logger.error(f"Failed to query Notion DB: {e}")
        return

    system_tz_str = os.getenv("SYSTEM_TIMEZONE", "America/New York")
    system_tz = pytz.timezone(system_tz_str)

    for page in pages:
        try:
            title_array = page['properties']['Name']['title']
            if not title_array:
                logger.warning("Skipping page with empty Name property.")
                continue

            title = title_array[0]['plain_text']
            url = page['properties'].get('URL', {}).get('url', '')
            content = fetch_and_parse_blocks_dropbox(page['id'], headers)

            # Construct the Dropbox path for the MD file
            filename = sanitize_filename(title) + '.md'
            dropbox_file_path = f"{knowledge_hub_path}/{filename}"

            # Check if file exists in Dropbox
            try:
                dbx.files_get_metadata(dropbox_file_path)
                logger.warning(f"File '{filename}' already exists in Dropbox. Skipping.")
                continue
            except dropbox.exceptions.ApiError as ex:
                # If "not_found", proceed; otherwise, raise
                if not (ex.error.is_path() and ex.error.get_path().is_not_found()):
                    raise ex

            created_time_utc = datetime.fromisoformat(page['created_time'].rstrip('Z')).replace(tzinfo=timezone.utc)
            local_created_time = created_time_utc.astimezone(system_tz)
            
            formatted_date = local_created_time.strftime("%b %-d, %Y")  
            now_str = datetime.now(timezone.utc).astimezone(system_tz).isoformat()

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

            # Upload to Dropbox
            dbx.files_upload(
                markdown_content.encode('utf-8'),
                dropbox_file_path,
                mode=dropbox.files.WriteMode.overwrite
            )
            logger.info(f"Uploaded '{filename}' to Dropbox: {dropbox_file_path}")

        except Exception as e:
            logger.error(f"Error processing Notion page {page.get('id')}: {e}")


# MASTER MAIN
def main():
    """
    1) Get the last synced timestamp from Redis.
    2) Run YouTube->Notion using that timestamp.
    3) Run Notion->Dropbox using the same timestamp (so newly added YouTube pages get exported).
    4) Finally, update the Redis timestamp, so next run starts fresh.
    """
    # Step 1: Retrieve or default
    last_synced_time = get_last_synced_knowledge_hub_at()
    if not last_synced_time:
        logger.info("No existing synced timestamp found. Will default to 1 day ago if needed.")
        # We'll allow each flow to handle if it's None or not.

    # Step 2: YouTube->Notion
    youtube_to_notion_main(last_checked_at=last_synced_time)

    # Step 3: Notion->Dropbox
    notion_to_dropbox_main(last_checked_at=last_synced_time)

    # Step 4: Now that both flows are done, update Redis
    update_last_synced_knowledge_hub_at()

if __name__ == '__main__':
    main()

