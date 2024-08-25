import os
import pickle
import base64
import re
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

credentials_path = os.getenv('GMAIL_CREDENTIALS_PATH')
print(f"Credentials Path: {credentials_path}")

if not credentials_path:
    raise ValueError("Environment variable GMAIL_CREDENTIALS_PATH must be set")

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            creds.refresh(Request())
        else:
            print("Initiating OAuth2 authorization flow...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    print("Credentials obtained successfully.")
    return build('gmail', 'v1', credentials=creds)

def clean_subject(subject):
    # Remove 'Watch "' from the beginning and '" on YouTube' from the end
    return re.sub(r'^Watch "(.+)" on YouTube$', r'\1', subject)

def extract_url(snippet):
    # Extract URL from the snippet
    url_match = re.search(r'(https?://\S+)', snippet)
    return url_match.group(1) if url_match else None

def search_messages(service, user_id='me', max_results=500):
    try:
        query = "from:genesisdayrit@gmail.com subject:Watch"
        youtube_shares = []
        page_token = None
        total_processed = 0

        while total_processed < max_results:
            results = service.users().messages().list(
                userId=user_id, 
                q=query, 
                pageToken=page_token, 
                maxResults=min(100, max_results - total_processed)
            ).execute()
            
            messages = results.get('messages', [])
            if not messages:
                break

            for message in messages:
                msg = service.users().messages().get(userId=user_id, id=message['id']).execute()
                payload = msg['payload']
                headers = payload['headers']
                
                # Get subject and clean it
                subject = next(header['value'] for header in headers if header['name'] == 'Subject')
                clean_title = clean_subject(subject)
                
                # Get URL from snippet
                url = extract_url(msg['snippet'])
                
                if url:
                    youtube_shares.append({'title': clean_title, 'url': url})

                total_processed += 1
                if total_processed >= max_results:
                    break

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        print(f"Total emails processed: {total_processed}")
        return youtube_shares

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def main():
    try:
        print("Initializing Gmail service...")
        service = get_gmail_service()
        print("Searching for YouTube share emails...")
        youtube_shares = search_messages(service, max_results=500)  # Set the number of emails to search
        
        if youtube_shares:
            print(f"Found {len(youtube_shares)} YouTube share emails:")
            for i, share in enumerate(youtube_shares, 1):
                print(f"\n{i}. Title: {share['title']}")
                print(f"   URL: {share['url']}")
        else:
            print('No YouTube share emails found.')
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()