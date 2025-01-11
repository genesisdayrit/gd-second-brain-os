import os
import json
import urllib.parse
from dotenv import load_dotenv

# Load environment variables from the .env file in the project root
project_root_path = os.getenv("PROJECT_ROOT_PATH")
if not project_root_path:
    raise EnvironmentError("Environment variable PROJECT_ROOT_PATH is not set.")

dotenv_path = os.path.join(project_root_path, ".env")
load_dotenv(dotenv_path)

# Path to the JSON credentials file
CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH")
if not CREDENTIALS_PATH:
    raise EnvironmentError("Environment variable GMAIL_CREDENTIALS_PATH is not set.")

# Load credentials from the JSON file
with open(CREDENTIALS_PATH, "r") as file:
    credentials = json.load(file)["installed"]

CLIENT_ID = credentials["client_id"]
REDIRECT_URI = credentials["redirect_uris"][0]
SCOPES = "https://www.googleapis.com/auth/gmail.readonly"

# Generate the authorization URL
auth_url = "https://accounts.google.com/o/oauth2/auth"
params = {
    "client_id": CLIENT_ID,
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPES,
    "access_type": "offline",
    "prompt": "consent",
}
auth_url_with_params = f"{auth_url}?{urllib.parse.urlencode(params)}"

print(f"Go to the following URL to authorize:\n{auth_url_with_params}")
