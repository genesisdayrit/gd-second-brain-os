import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from the initial .env file to get PROJECT_ROOT_PATH
load_dotenv()

# Get the PROJECT_ROOT_PATH
PROJECT_ROOT_PATH = os.getenv('PROJECT_ROOT_PATH')

# Ensure the PROJECT_ROOT_PATH is set
if not PROJECT_ROOT_PATH:
    raise EnvironmentError("Error: PROJECT_ROOT_PATH environment variable not set")

# Construct the path to the .env file in the project root and load it
env_path = Path(PROJECT_ROOT_PATH) / '.env'
load_dotenv(dotenv_path=env_path)

# Check if the environment variables are set
client_id = os.getenv('DROPBOX_ACCESS_KEY')
client_secret = os.getenv('DROPBOX_ACCESS_SECRET')
authorization_code = os.getenv('DROPBOX_AUTHORIZATION_CODE')
redirect_uri = 'http://localhost:5000'  # Use the same redirect URI as in your authorization URL

# Print environment variables to verify
print(f"PROJECT_ROOT_PATH: {PROJECT_ROOT_PATH}")
print(f"DROPBOX_CLIENT_ID: {client_id}")
print(f"DROPBOX_CLIENT_SECRET: {client_secret}")
print(f"DROPBOX_AUTHORIZATION_CODE: {authorization_code}")

# Ensure that all necessary environment variables are set
if not client_id or not client_secret or not authorization_code:
    raise EnvironmentError("Error: One or more required environment variables (DROPBOX_CLIENT_ID, DROPBOX_CLIENT_SECRET, DROPBOX_AUTHORIZATION_CODE) are not set")

def get_refresh_token():
    url = 'https://api.dropbox.com/oauth2/token'
    data = {
        'code': authorization_code,
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri
    }

    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        response_data = response.json()
        access_token = response_data.get('access_token')
        refresh_token = response_data.get('refresh_token')
        expires_in = response_data.get('expires_in')

        print(f"Access Token: {access_token}")
        print(f"Refresh Token: {refresh_token}")
        print(f"Expires In: {expires_in} seconds")

        # Return the tokens for use in other scripts if needed
        return access_token, refresh_token
    else:
        print(f"Error: {response.status_code} - {response.content}")
        return None, None

if __name__ == "__main__":
    access_token, refresh_token = get_refresh_token()
    if access_token and refresh_token:
        print("Token exchange was successful.")
    else:
        print("Token exchange failed.")

