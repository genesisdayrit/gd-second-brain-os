import os
import dropbox
import re
from datetime import datetime, timedelta
import pytz
import redis
from dotenv import load_dotenv
from pathlib import Path
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from openai import OpenAI

# Load environment variables
load_dotenv()

# Redis Configuration
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

def get_dropbox_access_token():
    """Retrieve Dropbox access token from Redis."""
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Dropbox Client Initialization
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# OpenAI API Key
openai_api_key = os.getenv('OPENAI_API_KEY')

def find_daily_folder(vault_path):
    """Search for the '_Daily' folder in the specified vault path."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily' in Dropbox")

def find_daily_action_folder(daily_folder_path):
    """Search for the '_Daily-Action' folder inside the '_Daily' folder."""
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
    
    latest_file = max(files, key=lambda x: x.client_modified)
    _, response = dbx.files_download(latest_file.path_lower)
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

def find_weekly_map(vault_path):
    """Locate and extract the content of this week's map."""
    def find_weekly_folder():
        response = dbx.files_list_folder(vault_path)
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly"):
                return entry.path_lower
        raise FileNotFoundError("Could not find a folder ending with '_Weekly' in Dropbox")

    def find_weekly_maps_folder(weekly_folder_path):
        response = dbx.files_list_folder(weekly_folder_path)
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly-Maps"):
                return entry.path_lower
        raise FileNotFoundError("Could not find a folder ending with '_Weekly-Maps' in Dropbox")

    def find_this_weeks_map(files):
        today = datetime.now()
        days_until_sunday = (6 - today.weekday()) % 7
        next_sunday = today + timedelta(days=days_until_sunday)
        sunday_str = next_sunday.strftime("%Y-%m-%d").lower()
        for file in files:
            if isinstance(file, dropbox.files.FileMetadata) and f"weekly map {sunday_str}" in file.name.lower():
                return file
        raise FileNotFoundError("Could not find this week's map.")

    weekly_folder_path = find_weekly_folder()
    weekly_maps_folder_path = find_weekly_maps_folder(weekly_folder_path)

    files = [
        entry for entry in dbx.files_list_folder(weekly_maps_folder_path).entries
        if isinstance(entry, dropbox.files.FileMetadata)
    ]
    weekly_map_file = find_this_weeks_map(files)

    _, response = dbx.files_download(weekly_map_file.path_lower)
    return response.content.decode('utf-8')

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

def send_email(subject, daily_prep, todays_plan, weekly_map, to_email, from_email, password):
    """Send an email with the daily prep, today's plan, and weekly map."""
    try:
        s = smtplib.SMTP(host='smtp.gmail.com', port=587)
        s.starttls()
        s.login(from_email, password)

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject

        daily_prep_html = f"<h3>Daily Prep:</h3>{daily_prep.replace('\n', '<br>')}"
        todays_plan_html = f"<h3>Today's Plan:</h3>{todays_plan.replace('\n', '<br>')}"
        weekly_map_html = f"<h3>Weekly Map:</h3>{weekly_map.replace('\n', '<br>')}"

        message_body = f"{daily_prep_html}<br><hr><br>{todays_plan_html}<br><hr><br>{weekly_map_html}"
        msg.attach(MIMEText(message_body, 'html'))

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
        # Fetch daily content
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        daily_action_folder_path = find_daily_action_folder(daily_folder_path)
        latest_file_contents = fetch_latest_file(daily_action_folder_path)
        extracted_text = extract_section(latest_file_contents)

        # Fetch weekly map content
        weekly_map_content = find_weekly_map(dropbox_vault_path)

        # Get OpenAI response
        ai_response = get_openai_response(extracted_text)

        # Current date in mm/dd/yyyy format
        current_date = datetime.now().strftime("%m/%d/%Y")

        # Send the email
        send_email(
            subject=f"Daily Vision AM Check-In ({current_date})",
            daily_prep=ai_response,
            todays_plan=extracted_text,
            weekly_map=weekly_map_content,
            to_email=to_email,
            from_email=from_email,
            password=password
        )
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

