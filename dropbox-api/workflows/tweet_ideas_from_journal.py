import os
import dropbox
from datetime import datetime
import redis
from dotenv import load_dotenv
from openai import OpenAI
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pytz import timezone

# Load environment variables from .env file
load_dotenv()

# Redis configuration
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Function to get the Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Retrieve Dropbox and OpenAI API configurations
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
openai_api_key = os.getenv('OPENAI_API_KEY')

# Initialize Dropbox client
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# Function to load prompts from an external file
def load_prompts(prompt_file_path):
    """Load system prompt and style description from an external file."""
    if not os.path.exists(prompt_file_path):
        raise FileNotFoundError(f"Prompt file not found: {prompt_file_path}")
    
    prompts = {}
    with open(prompt_file_path, 'r') as file:
        current_key = None
        for line in file:
            line = line.strip()
            if line.endswith(":"):
                current_key = line[:-1]
                prompts[current_key] = ""
            elif current_key:
                prompts[current_key] += f"{line} "
    
    return prompts.get("SYSTEM_PROMPT", "").strip(), prompts.get("STYLE_DESCRIPTION", "").strip()

def find_daily_folder(vault_path):
    """Search for the '_Daily' folder in the specified vault path."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Daily"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Daily' in Dropbox")

def find_journal_folder(daily_folder_path):
    """Search for the '_Journal' folder inside the '_Daily' folder."""
    response = dbx.files_list_folder(daily_folder_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Journal"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Journal' in Dropbox")

def fetch_today_journal_entry(journal_folder_path):
    """Fetch today's journal entry from the '_Journal' folder."""
    eastern = timezone('US/Eastern')
    now_eastern = datetime.now(eastern)
    today_date = now_eastern.strftime("%b %-d, %Y").lower()  # e.g., "dec 10, 2024"

    # List all files in the folder
    result = dbx.files_list_folder(journal_folder_path)
    all_files = []

    # Collect all files across batches
    while True:
        all_files.extend([
            entry for entry in result.entries if isinstance(entry, dropbox.files.FileMetadata)
        ])
        if not result.has_more:
            break
        result = dbx.files_list_folder_continue(result.cursor)

    # Search for today's file
    for entry in all_files:
        file_name = entry.name.strip().lower()  # Ensure lowercase
        if file_name == f"{today_date}.md":  # Match today's file
            # Download and return the file contents
            metadata, response = dbx.files_download(entry.path_lower)
            return response.content.decode('utf-8')

    # Raise an error if no match is found
    raise FileNotFoundError(f"Today's journal entry ({today_date}) not found in the '_Journal' folder.")

def get_tweet_ideas_from_openai(journal_text, system_prompt, style_description):
    """Generate tweet ideas from today's journal text using OpenAI GPT-4."""
    client = OpenAI(api_key=openai_api_key)
    user_prompt = f"""here is today's journal entry:

{journal_text}

{style_description.strip()}"""

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content

def send_email(subject, tweet_ideas, to_email, from_email, password):
    """Send an email with the tweet ideas."""
    try:
        s = smtplib.SMTP(host='smtp.gmail.com', port=587)
        s.starttls()
        s.login(from_email, password)

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject

        # Ensure proper spacing between tweet ideas
        formatted_tweet_ideas = tweet_ideas.strip().replace('\n\n', '</p><p>').replace('\n', '<br>')

        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c5282;">Tweet Ideas</h2>
                    <div style="margin-bottom: 30px;">
                        <p>{formatted_tweet_ideas}</p>
                    </div>
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(html_content, 'html'))
        s.send_message(msg)
        s.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Error occurred while sending email: {e}")

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    prompt_file_path = "tweet_style_prompt.txt"
    from_email = os.getenv('GMAIL_ACCOUNT')
    password = os.getenv('GMAIL_PASSWORD')
    to_email = from_email  # or another recipient

    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return

    try:
        # Load prompts
        system_prompt, style_description = load_prompts(prompt_file_path)

        # Locate folders
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        journal_folder_path = find_journal_folder(daily_folder_path)

        # Fetch today's journal entry
        journal_text = fetch_today_journal_entry(journal_folder_path)

        # Generate tweet ideas
        tweet_ideas = get_tweet_ideas_from_openai(journal_text, system_prompt, style_description)
        current_date = datetime.now().strftime("%m/%d/%Y")

        # Send the email
        send_email(
            subject=f"Tweet Ideas ({current_date})",
            tweet_ideas=tweet_ideas,
            to_email=to_email,
            from_email=from_email,
            password=password
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

