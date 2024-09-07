import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

vault_path = os.getenv('OBSIDIAN_VAULT_BASE_PATH')  # Get the vault path from environment variable
one_day_ago = time.time() - 24 * 60 * 60  # Subtract 24 hours (in seconds) from the current time

if vault_path:
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith('.md'):  # Only check .md files
                file_path = os.path.join(root, file)
                if os.path.getmtime(file_path) > one_day_ago:
                    print(file_path)
else:
    print("OBSIDIAN_VAULT_BASE_PATH is not set")

