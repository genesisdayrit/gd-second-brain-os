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
                
                # Fetch modification and creation times
                modification_time = os.path.getmtime(file_path)
                creation_time = os.path.getctime(file_path)

                # Check if the file was modified or created in the last day
                if modification_time > one_day_ago or creation_time > one_day_ago:
                    print(f"File: {file_path}")
                    print(f"  Last Modified: {time.ctime(modification_time)}")
                    print(f"  Creation/Metadata Changed: {time.ctime(creation_time)}\n")
else:
    print("OBSIDIAN_VAULT_BASE_PATH is not set")

