import os
import pickle
import base64
import re
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from notion_client import Client
import hashlib
from datetime import datetime, timezone
from google.oauth2.service_account import Credentials

load_dotenv()

# Load environment variables
credentials_path = os.getenv('GMAIL_CREDENTIALS_PATH')
notion_api_key = os.getenv('NOTION_API_KEY')
notion_knowledge_hub_db = os.getenv('NOTION_KNOWLEDGE_HUB_DB')
GDRIVE_CREDENTIALS_PATH = os.getenv('GDRIVE_CREDENTIALS_PATH')
GOOGLE_SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')
youtube_saves_email_address = os.getenv('YOUTUBE_SAVES_EMAIL_ADDRESS')

# Check if all required environment variables are set
if not all([
    credentials_path,
    notion_api_key,
    notion_knowledge_hub_db,
    GDRIVE_CREDENTIALS_PATH,
    GOOGLE_SPREADSHEET_ID,
    youtube_saves_email_address
]):
    raise ValueError("All required environment variables must be set")

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/spreadsheets']

notion = Client(auth=notion_api_key)

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

def get_sheets_service():
    creds = Credentials.from_service_account_file(GDRIVE_CREDENTIALS_PATH, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def print_google_sheet_link():
    sheet_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SPREADSHEET_ID}"
    print(f"Google Sheet link for checking logs: {sheet_url}")

def clean_subject(subject):
    return re.sub(r'^Watch "(.+)" on YouTube$', r'\1', subject)

def extract_url(snippet):
    url_match = re.search(r'(https?://\S+)', snippet)
    return url_match.group(1) if url_match else None

def check_existing_entry(url):
    results = notion.databases.query(
        database_id=notion_knowledge_hub_db,
        filter={
            "property": "URL",
            "url": {
                "equals": url
            }
        }
    ).get("results")
    return len(results) > 0

def add_to_notion(title, url):
    notion.pages.create(
        parent={"database_id": notion_knowledge_hub_db},
        properties={
            "Name": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url}
        }
    )
    print(f"Added to Notion: {title}")

def get_last_checked_timestamp():
    service = get_sheets_service()
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range='gmail-checker-logs!A2:A'
    ).execute()
    values = result.get('values', [])
    if not values:
        return None
    last_timestamp = values[-1][0]
    return datetime.strptime(last_timestamp, '%m/%d/%Y %H:%M:%S').replace(tzinfo=timezone.utc)

def update_checked_timestamp():
    service = get_sheets_service()
    now = datetime.now(timezone.utc).strftime('%m/%d/%Y %H:%M:%S')
    service.spreadsheets().values().append(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        range='gmail-checker-logs!A:A',
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
        body={'values': [[now]]}
    ).execute()
    print(f"Timestamp updated: {now}")

def search_messages(service, user_id='me', last_checked_at=None):
    try:
        query = f"from:{youtube_saves_email_address} subject:Watch"
        if last_checked_at:
            query += f" after:{last_checked_at.strftime('%Y/%m/%d')}"

        print(f"Using Gmail query: {query}")

        youtube_shares = []
        results = service.users().messages().list(
            userId=user_id, 
            q=query
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            print("No messages found matching the query.")
            return []

        print(f"Found {len(messages)} messages matching the query.")

        for message in messages:
            msg = service.users().messages().get(userId=user_id, id=message['id']).execute()

            msg_date = datetime.fromtimestamp(int(msg['internalDate'])/1000, tz=timezone.utc)

            print(f"Processing message from {msg_date}")

            if last_checked_at and msg_date <= last_checked_at:
                print(f"Skipping message: not newer than last checked timestamp ({last_checked_at})")
                continue

            payload = msg['payload']
            headers = payload['headers']

            subject = next(header['value'] for header in headers if header['name'] == 'Subject')
            clean_title = clean_subject(subject)

            url = extract_url(msg['snippet'])

            if not url:
                print(f"Skipping message: no URL found in snippet")
                continue

            if check_existing_entry(url):
                print(f"Skipping message: URL already exists in Notion")
                continue

            youtube_shares.append({'title': clean_title, 'url': url})
            print(f"Added to processing list: {clean_title}")

        print(f"Total emails processed: {len(messages)}")
        print(f"New YouTube shares found: {len(youtube_shares)}")
        return youtube_shares

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

def main():
    try:
        print("Initializing Gmail service...")
        service = get_gmail_service()

        last_checked_at = get_last_checked_timestamp()
        if last_checked_at:
            print(f"Searching for YouTube share emails since {last_checked_at}...")
        else:
            print("No previous check timestamp found. Searching all emails...")

        youtube_shares = search_messages(service, last_checked_at=last_checked_at)

        if youtube_shares:
            print(f"Found {len(youtube_shares)} new YouTube share emails:")
            for share in youtube_shares:
                add_to_notion(share['title'], share['url'])
        else:
            print('No new YouTube share emails found.')

        update_checked_timestamp()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()
    print_google_sheet_link()  # Print the Google Sheet link for easy access

