import os
import json
import requests
import redis

# Redis connection
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)

# Path to the JSON credentials file
CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH")
if not CREDENTIALS_PATH:
    raise EnvironmentError("Environment variable GMAIL_CREDENTIALS_PATH is not set.")

# Load credentials from the JSON file
with open(CREDENTIALS_PATH, "r") as file:
    credentials = json.load(file)["installed"]

CLIENT_ID = credentials["client_id"]
CLIENT_SECRET = credentials["client_secret"]

def refresh_access_token():
    """Refresh the Gmail API access token and store it in Redis."""
    refresh_token = redis_client.get("gmail_refresh_token")

    if not refresh_token:
        raise ValueError("No refresh token found in Redis. Please run the initial setup first.")

    # Token refresh request
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    response = requests.post(token_url, data=data)

    if response.status_code == 200:
        tokens = response.json()
        new_access_token = tokens["access_token"]

        # Store the new access token in Redis
        redis_client.set("gmail_access_token", new_access_token)

        print(f"New Access Token: {new_access_token}")
    else:
        print(f"Failed to refresh token: {response.status_code}")
        print(response.text)

# Run the refresh token function
refresh_access_token()
