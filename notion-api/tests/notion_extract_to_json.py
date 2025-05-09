import os
import json
import requests
from dotenv import load_dotenv
from pathlib import Path
from notion_client import Client
from datetime import datetime, timezone, timedelta
import logging
import pytz

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the path to the .env file relative to the script's location
env_path = Path(__file__).resolve().parent.parent / '.env'

# Load environment variables from the .env file
load_dotenv(dotenv_path=env_path)

# --- Timezone Configuration ---
timezone_str = os.getenv("SYSTEM_TIMEZONE", "US/Eastern")
system_tz = pytz.timezone(timezone_str)
logger.info(f"Using system timezone: {timezone_str}")

# Retrieve environment variables
notion_api_key = os.getenv('NOTION_API_KEY')
notion_knowledge_hub_db = os.getenv('NOTION_KNOWLEDGE_HUB_DB')

# Ensure the critical environment variables are loaded
if not notion_api_key:
    raise ValueError("NOTION_API_KEY environment variable is not set.")
if not notion_knowledge_hub_db:
    raise ValueError("NOTION_KNOWLEDGE_HUB_DB environment variable is not set.")

# Initialize Notion client
notion = Client(auth=notion_api_key)

# Convert the target date and time to UTC for comparison
# Replace hardcoded Central Time with system timezone
target_datetime = datetime(2024, 8, 11, 15, 0, tzinfo=system_tz)
target_datetime_utc = target_datetime.astimezone(timezone.utc)
logger.info(f"Target datetime in {timezone_str}: {target_datetime}")
logger.info(f"Target datetime in UTC: {target_datetime_utc}")

# Get the database name for creating a subfolder
database_name = notion.databases.retrieve(notion_knowledge_hub_db)['title'][0]['plain_text']

# Ensure the destination path exists
destination_path = Path('database-extractions') / database_name
destination_path.mkdir(parents=True, exist_ok=True)

# Function to fetch blocks and parse content recursively
def fetch_and_parse_blocks(block_id, headers):
    blocks_url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    response = requests.get(blocks_url, headers=headers)
    response.raise_for_status()
    data_blocks = response.json()

    markdown_content = ""
    for block in data_blocks["results"]:
        block_type = block["type"]

        # Parse block based on its type
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

        # Handle nested blocks (children)
        if block.get("has_children"):
            markdown_content += fetch_and_parse_blocks(block["id"], headers)

    return markdown_content

# Helper functions for each block type
def parse_paragraph(block):
    text = extract_text(block["paragraph"]["rich_text"])
    return f"{text}\n\n"

def parse_heading(block, block_type):
    text = extract_text(block[block_type]["rich_text"])
    level = block_type.split("_")[-1]
    return f"{'#' * int(level)} {text}\n\n"

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

def parse_image(block):
    image_url = block["image"].get("file", {}).get("url", block["image"].get("external", {}).get("url", ""))
    return f"![Image]({image_url})\n\n"

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

# Process and collect results
results = []
headers = {
    "Authorization": f"Bearer {notion_api_key}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# Query the Notion database with a filter based on Created time
for page in notion.databases.query(
    **{
        "database_id": notion_knowledge_hub_db,
        "filter": {
            "property": "Created",
            "date": {
                "after": target_datetime_utc.isoformat()
            }
        },
        "sorts": [
            {
                "property": "Created",
                "direction": "descending"
            }
        ]
    }
)["results"]:
    title = page['properties']['Name']['title'][0]['plain_text']
    url = page['properties']['URL']['url'] if 'URL' in page['properties'] else None
    content = fetch_and_parse_blocks(page['id'], headers)
    
    # Get the creation date from Notion and convert to local time
    created_time_utc = datetime.fromisoformat(page['created_time'].rstrip('Z')).replace(tzinfo=timezone.utc)
    created_time_local = created_time_utc.astimezone(system_tz)
    formatted_date = created_time_local.strftime("%b %-d, %Y")  # Format: Aug 24, 2024 or Aug 3, 2024
    
    results.append({
        "title": title,
        "url": url,
        "content": f"---\nRelated Journal: [[{formatted_date}]]\n---\n\n{content}"
    })

# Generate a filename with a timestamp
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
json_filename = f'extracted_content_{timestamp}.json'

# Save the results to a JSON file in the destination path
json_filepath = destination_path / json_filename
with open(json_filepath, 'w') as json_file:
    json.dump(results, json_file, indent=4)

logger.info(f"JSON file created: {json_filepath}")