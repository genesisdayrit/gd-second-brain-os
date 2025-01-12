import os
import re
import redis
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from notion_client import Client
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials

# Load environment variables from the .env file
load_dotenv()

# Redis connection
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Load environment variables
notion_api_key = os.getenv('NOTION_API_KEY')
notion_knowledge_hub_db = os.getenv('NOTION_KNOWLEDGE_HUB_DB')
youtube_saves_email_address = os.getenv('YOUTUBE_SAVES_EMAIL_ADDRESS')

# Check if all required environment variables are set
if not all([
    notion_api_key,
    notion_knowledge_hub_db,
    youtube_saves_email_address
]):
    raise ValueError("All required environment variables must be set")

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Initialize the Notion client
notion = Client(auth=notion_api_key)


def get_gmail_service():
    """Retrieve Gmail API service using Redis-stored access token."""
    access_token = redis_client.get("gmail_access_token")

    if not access_token:
        raise ValueError("No access token found in Redis. Ensure tokens are set up and refreshed properly.")

    creds = Credentials(
        token=access_token,
        refresh_token=None,  # Redis handles refresh tokens, so this isn't needed here.
        token_uri="https://oauth2.googleapis.com/token",
        client_id=None,
        client_secret=None,
    )

    if creds.expired:
        raise ValueError("Access token expired. Run the token refresh process to update Redis.")

    return build('gmail', 'v1', credentials=creds)


def clean_subject(subject):
    """Clean the email subject line."""
    return re.sub(r'^Watch "(.+)" on YouTube$', r'\1', subject)


def extract_url(snippet):
    """Extract a URL from the email snippet."""
    url_match = re.search(r'(https?://\S+)', snippet)
    return url_match.group(1) if url_match else None


def check_existing_entry(url):
    """Check if the URL already exists in the Notion database."""
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
    """Add a new entry to the Notion database."""
    notion.pages.create(
        parent={"database_id": notion_knowledge_hub_db},
        properties={
            "Name": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url}
        }
    )
    print(f"Added to Notion: {title}")


def get_last_checked_timestamp():
    """Retrieve the last checked timestamp for YouTube Gmail from Redis."""
    last_checked = redis_client.get("youtube_gmail_last_checked_at")
    if last_checked:
        return datetime.strptime(last_checked, '%Y-%m-%dT%H:%M:%S%z')
    return None


def update_checked_timestamp():
    """Update the last checked timestamp for YouTube Gmail in Redis."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z')
    redis_client.set("youtube_gmail_last_checked_at", now)
    print(f"Timestamp updated in Redis: {now}")


def search_messages(service, user_id='me', last_checked_at=None):
    """Search for messages in Gmail."""
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

            msg_date = datetime.fromtimestamp(int(msg['internalDate']) / 1000, tz=timezone.utc)

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
    """Main entry point."""
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
