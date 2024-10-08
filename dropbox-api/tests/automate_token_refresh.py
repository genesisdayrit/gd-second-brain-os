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
refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')

# Print environment variables to verify
print(f"PROJECT_ROOT_PATH: {PROJECT_ROOT_PATH}")
print(f"DROPBOX_ACCESS_KEY: {client_id}")
print(f"DROPBOX_ACCESS_SECRET: {client_secret}")
print(f"DROPBOX_REFRESH_TOKEN: {refresh_token}")

# Ensure that all necessary environment variables are set
if not client_id or not client_secret or not refresh_token:
    raise EnvironmentError("Error: One or more required environment variables (DROPBOX_ACCESS_TOKEN, DROPBOX_ACCESS_SECRET, DROPBOX_REFRESH_TOKEN) are not set")

def refresh_access_token():
    url = 'https://api.dropbox.com/oauth2/token'
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret
    }

    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        response_data = response.json()
        access_token = response_data.get('access_token')
        expires_in = response_data.get('expires_in')

        print(f"New Access Token: {access_token}")
        print(f"Expires In: {expires_in} seconds")

        # Optionally, update the .env file with the new access token
        # First, remove any old access token line from the .env file
        with open(env_path, 'r') as file:
            lines = file.readlines()
        with open(env_path, 'w') as file:
            for line in lines:
                if not line.startswith('DROPBOX_ACCESS_TOKEN='):
                    file.write(line)
            # Add the new access token
            file.write(f'DROPBOX_ACCESS_TOKEN={access_token}\n')

        return access_token
    else:
        print(f"Error: {response.status_code} - {response.content}")
        return None

if __name__ == "__main__":
    new_access_token = refresh_access_token()
    if new_access_token:
        print("Access token refresh was successful.")
    else:
        print("Access token refresh failed.")

