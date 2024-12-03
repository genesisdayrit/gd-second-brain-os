import os
import dropbox
import re
from datetime import datetime
import redis
from dotenv import load_dotenv
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

def fetch_latest_file_contents(vault_path):
    """Fetch the latest file content from Dropbox."""
    try:
        response = dbx.files_list_folder(vault_path)
        files = [
            entry for entry in response.entries
            if isinstance(entry, dropbox.files.FileMetadata)
        ]
        if not files:
            raise FileNotFoundError("No files found in the specified folder.")
        latest_file = max(files, key=lambda x: x.client_modified)
        _, response = dbx.files_download(latest_file.path_lower)
        return response.content.decode('utf-8')
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Could not fetch latest file: {e}")

def extract_section(file_contents):
    """Extract the section starting with 'Vision Objective 1:' and ending with '---'."""
    pattern = r"(Vision Objective 1:.*?---)"
    match = re.search(pattern, file_contents, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        raise ValueError("The expected section could not be found in the file.")

def get_openai_response_reflection(combined_text):
    """Get a response from OpenAI using the combined text for reflection."""
    client = OpenAI(api_key=openai_api_key)
    system_prompt = (
        "You are a curious, kind, and creative friend who is interested in supporting the user's vision "
        "and wanting the best for them. Imagine that the day is already over. You are skilled at asking "
        "the user smart questions and prompts that help them reflect on their day and think about what "
        "actions they took towards moving towards their vision and goals today and this week."
    )
    user_prompt = combined_text

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content

def send_email(subject, extracted_text, ai_response, to_email, from_email, password):
    """Send an email with the extracted note content and AI response."""
    try:
        s = smtplib.SMTP(host='smtp.gmail.com', port=587)
        s.starttls()
        s.login(from_email, password)

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject

        formatted_extracted_text = f"<h3>Today's Plan:</h3>{extracted_text.replace('\n', '<br>')}"
        formatted_ai_response = f"<h3>Reflection:</h3>{ai_response.replace('\n', '<br>')}"
        message_body = f"{formatted_extracted_text}<br><hr><br>{formatted_ai_response}"
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
        # Fetch latest file content
        latest_file_contents = fetch_latest_file_contents(dropbox_vault_path)
        extracted_text = extract_section(latest_file_contents)

        # Get OpenAI reflection response
        ai_response = get_openai_response_reflection(extracted_text)

        # Current date in mm/dd/yyyy format
        current_date = datetime.now().strftime("%m/%d/%Y")

        # Send the email
        send_email(
            subject=f"Daily Vision PM Check In ({current_date})",
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
