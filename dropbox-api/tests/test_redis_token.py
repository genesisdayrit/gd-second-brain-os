import os
from dotenv import load_dotenv
import redis
import dropbox

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)  

# Connect to Redis using the environment variables
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)


# Retrieve the Dropbox access token from Redis
DROPBOX_ACCESS_TOKEN = r.get('DROPBOX_ACCESS_TOKEN')

if not DROPBOX_ACCESS_TOKEN:
    print("Error: Dropbox access token not found in Redis.")
else:
    print(f"Retrieved Dropbox Access Token: {DROPBOX_ACCESS_TOKEN}")

    # Initialize Dropbox client using the token from Redis
    dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

    # Test connection by listing contents of the root folder in Dropbox
    try:
        result = dbx.files_list_folder('')
        print("Files in the root folder:")
        for entry in result.entries:
            print(f" - {entry.name}")
    except dropbox.exceptions.ApiError as e:
        print(f"Error accessing Dropbox API: {e}")

