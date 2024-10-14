import os
from dotenv import load_dotenv
import urllib.parse

# Load environment variables from .env file
load_dotenv()

# Get Dropbox App Key and Secret from environment variables
DROPBOX_ACCESS_KEY = os.getenv('DROPBOX_ACCESS_KEY')
DROPBOX_ACCESS_SECRET = os.getenv('DROPBOX_ACCESS_SECRET')
REDIRECT_URI = 'http://localhost:5000'  # Modify this if your app uses a different redirect URI

# Construct the authorization URL with offline access (to get a refresh token)
def create_authorization_url():
    base_url = 'https://www.dropbox.com/oauth2/authorize'
    params = {
        'client_id': DROPBOX_ACCESS_KEY,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'token_access_type': 'offline'  # Request a refresh token
    }
    query_string = urllib.parse.urlencode(params)
    auth_url = f"{base_url}?{query_string}"
    return auth_url

def main():
    auth_url = create_authorization_url()
    print("Go to the following URL to authorize the app:")
    print(auth_url)

if __name__ == "__main__":
    main()


