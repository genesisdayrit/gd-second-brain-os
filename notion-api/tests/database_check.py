import os
from notion_client import Client
from dotenv import load_dotenv
from pathlib import Path

# Load the project root path
project_root_path = os.getenv('PROJECT_ROOT_PATH')

# Ensure PROJECT_ROOT_PATH is loaded
if not project_root_path:
    raise ValueError("PROJECT_ROOT_PATH environment variable is not set.")

# Load environment variables from the .env file located at the project root
env_path = Path(project_root_path) / '.env'
load_dotenv(dotenv_path=env_path)

# Retrieve other environment variables
notion_api_key = os.getenv('NOTION_API_KEY')
notion_knowledge_hub_db = os.getenv('NOTION_KNOWLEDGE_HUB_DB')

# Ensure the critical environment variables are loaded
if not notion_api_key:
    raise ValueError("NOTION_API_KEY environment variable is not set.")
if not notion_knowledge_hub_db:
    raise ValueError("NOTION_KNOWLEDGE_HUB_DB environment variable is not set.")

# Initialize Notion client
notion = Client(auth=notion_api_key)

# Query the database for the last 3 pages sorted by creation time
response = notion.databases.query(
    **{
        "database_id": notion_knowledge_hub_db,
        "sorts": [
            {
                "property": "Created",
                "direction": "descending"
            }
        ],
        "page_size": 3
    }
)

# Process and print results
for page in response.get('results', []):
    title = page['properties']['Name']['title'][0]['plain_text']
    created_time = page['created_time']
    print(f"Title: {title}, Created Time: {created_time}")

