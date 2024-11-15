import os
import dropbox
import re
from datetime import datetime
import pytz
import redis
from dotenv import load_dotenv
from pathlib import Path
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')  # Default to 'localhost' if not set
redis_port = int(os.getenv('REDIS_PORT', 6379))    # Default to 6379 if not set
redis_password = os.getenv('REDIS_PASSWORD', None)  # Default to None if not set

# Connect to Redis using the environment variables
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Function to get the Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Get the PROJECT_ROOT_PATH
PROJECT_ROOT_PATH = os.getenv('PROJECT_ROOT_PATH')

# Ensure the PROJECT_ROOT_PATH is set
if not PROJECT_ROOT_PATH:
    raise EnvironmentError("Error: PROJECT_ROOT_PATH environment variable not set")

# Construct the path to the .env file and load it
env_path = Path(PROJECT_ROOT_PATH) / '.env'
load_dotenv(dotenv_path=env_path)

# Retrieve the Dropbox access token from Redis
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()

# Initialize Dropbox client using the token from Redis
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# Get OpenAI API key
openai_api_key = os.getenv('OPENAI_API_KEY')

def find_daily_folder(vault_path):
    """Search for the '_Daily' folder in the specified vault path."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily' in Dropbox")

def find_daily_action_folder(daily_folder_path):
    """Search for the '_Daily-Action' folder inside the specified daily folder."""
    response = dbx.files_list_folder(daily_folder_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily-Action"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily-Action' in Dropbox")

def fetch_latest_file(daily_action_folder_path):
    """Fetch the latest file from the '_Daily-Action' folder."""
    response = dbx.files_list_folder(daily_action_folder_path)
    files = [
        entry for entry in response.entries
        if isinstance(entry, dropbox.files.FileMetadata)
    ]
    if not files:
        raise FileNotFoundError("No files found in the '_Daily-Action' folder.")
    
    # Sort files by client_modified date (most recent first)
    latest_file = max(files, key=lambda x: x.client_modified)
    metadata, response = dbx.files_download(latest_file.path_lower)
    file_contents = response.content.decode('utf-8')
    return file_contents

def extract_section(file_contents):
    """Extract the section starting with 'Vision Objective 1:' and ending with '---'."""
    pattern = r"(Vision Objective 1:.*?---)"
    match = re.search(pattern, file_contents, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        raise ValueError("The expected section could not be found in the file.")

def get_openai_response(combined_text):
    """Get a response from OpenAI using the combined text."""
    client = OpenAI(api_key=openai_api_key)
    system_prompt = (
        "You are a curious, kind, and creative friend who is interested in supporting the user's vision "
        "and wanting the best for them. You are skilled at making smart suggestions that will help the user "
        "meet their own goals and desires."
    )
    user_prompt = combined_text

    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content

def send_email(subject, extracted_text, ai_response, to_email, from_email, password):
    """Send an email with the extracted note content, AI response, and text."""
    try:
        # Set up the SMTP server
        s = smtplib.SMTP(host='smtp.gmail.com', port=587)
        s.starttls()
        s.login(from_email, password)

        # Create a message
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject

        # Format content
        formatted_extracted_text = f"<h3>Today's plan:</h3>{extracted_text.replace('\n', '<br>')}"
        formatted_ai_response = f"<h3>Daily Prep:</h3>{ai_response.replace('\n', '<br>')}"
        message_body = f"{formatted_extracted_text}<br><hr><br>{formatted_ai_response}"
        msg.attach(MIMEText(message_body, 'html'))

        # Send the message via the server
        s.send_message(msg)
        s.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Error occurred while sending email: {e}")

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    from_email = os.getenv('GMAIL_ACCOUNT')
    password = os.getenv('GMAIL_PASSWORD')
    to_email = from_email  # or another recipient

    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return
    try:
        # Locate folders
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        daily_action_folder_path = find_daily_action_folder(daily_folder_path)

        # Fetch the latest file and extract the relevant section
        latest_file_contents = fetch_latest_file(daily_action_folder_path)
        extracted_text = extract_section(latest_file_contents)

        # Get OpenAI response
        ai_response = get_openai_response(extracted_text)

        # Current date in mm/dd/yyyy format
        current_date = datetime.now().strftime("%m/%d/%Y")

        # Send the email
        send_email(
            subject=f"Daily Vision AM Check-In ({current_date})",
            extracted_text=extracted_text,
            ai_response=ai_response,
            to_email=to_email,
            from_email=from_email,
            password=password
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

