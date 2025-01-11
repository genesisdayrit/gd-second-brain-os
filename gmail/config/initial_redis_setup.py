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
REDIRECT_URI = credentials["redirect_uris"][0]

# Enter the authorization code from the browser
authorization_code = input("Enter the authorization code: ")

# Exchange the authorization code for tokens
token_url = "https://oauth2.googleapis.com/token"
data = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code": authorization_code,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
}

response = requests.post(token_url, data=data)

if response.status_code == 200:
    tokens = response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Store tokens in Redis
    redis_client.set("gmail_access_token", access_token)
    redis_client.set("gmail_refresh_token", refresh_token)

    print(f"Access Token: {access_token}")
    print(f"Refresh Token: {refresh_token}")
else:
    print(f"Failed to exchange authorization code: {response.status_code}")
    print(response.text)
