import os
import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define the scope for Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Path to your credentials JSON file
CREDENTIALS_PATH = os.getenv('GDRIVE_CREDENTIALS_PATH')

# Google Sheets document ID and sheet name
SPREADSHEET_ID = '1ky3HHYF_gpOFZHE3J9pGt-6J8cIyXoKmW80ZpeZR-_c'
SHEET_NAME = 'notion-export-logs'

def append_timestamp_to_sheet():
    # Load credentials and create a service instance
    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)

    # Get the current timestamp
    now = datetime.datetime.now().isoformat()

    # Append the timestamp to the sheet
    request = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f'{SHEET_NAME}!A:A',
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
        body={'values': [[now]]}
    )
    response = request.execute()
    print('Timestamp added:', response)

if __name__ == '__main__':
    append_timestamp_to_sheet()
