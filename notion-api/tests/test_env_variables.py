import os
from dotenv import load_dotenv
from pathlib import Path

# Define the path to the .env file relative to the script's location
env_path = Path(__file__).resolve().parent.parent / '.env'

# Load environment variables
load_dotenv(dotenv_path=env_path)

# Print environment variables
ROOT_PROJECT_PATH = os.getenv('PROJECT_ROOT_PATH')
NOTION_API_KEY = os.getenv('NOTION_API_KEY')
NOTION_KNOWLEDGE_HUB_DB = os.getenv('NOTION_KNOWLEDGE_HUB_DB')

print(f"ROOT_PROJECT_PATH: {ROOT_PROJECT_PATH}")
print(f"NOTION_API_KEY: {NOTION_API_KEY}")
print(f"NOTION_KNOWLEDGE_HUB_DB: {NOTION_KNOWLEDGE_HUB_DB}")

# Check if variables are None (optional)
if not ROOT_PROJECT_PATH:
    print("Error: ROOT_PROJECT_PATH environment variable is not set.")
if not NOTION_API_KEY:
    print("Error: NOTION_API_KEY environment variable is not set.")
if not NOTION_KNOWLEDGE_HUB_DB:
    print("Error: NOTION_KNOWLEDGE_HUB_DB environment variable is not set.")

