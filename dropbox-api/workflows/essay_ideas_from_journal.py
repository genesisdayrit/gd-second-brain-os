import os
import dropbox
from datetime import datetime
import redis
from dotenv import load_dotenv
from pathlib import Path
from openai import OpenAI
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pytz import timezone
from datetime import timedelta

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

def find_journal_folder(daily_folder_path):
    """Search for the '_Journal' folder inside the '_Daily' folder."""
    response = dbx.files_list_folder(daily_folder_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Journal"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Journal' in Dropbox")

def fetch_today_journal_entry(journal_folder_path):
    """
    Fetch today's journal entry from the '_Journal' folder, assuming lowercase file names.
    """
    # Set up timezones
    eastern = timezone('US/Eastern')
    utc = timezone('UTC')

    # Current time in Eastern Time and UTC
    now_eastern = datetime.now(eastern)
    today_date = now_eastern.strftime("%b %d, %Y").lower()  # e.g., "nov 15, 2024"

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

def get_essay_ideas_from_openai(journal_text):
    """Generate essay ideas from today's journal text using OpenAI GPT-4."""
    client = OpenAI(api_key=openai_api_key)
    system_prompt = (
        "You are a thoughtful and creative writer who generates insightful essay ideas "
        "based on the content provided. Focus on drawing themes, patterns, and unique angles "
        "from the provided text to create compelling essay topics. For each essay idea, "
        "provide a brief explanation of why it would be interesting to explore."
    )
    user_prompt = f"Here is today's journal entry:\n\n{journal_text}\n\nPlease suggest 3-5 essay ideas with brief explanations of why each would be worth exploring."

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content

def get_book_recommendations(journal_text):
    """Generate book recommendations based on journal content using OpenAI GPT-4."""
    client = OpenAI(api_key=openai_api_key)
    system_prompt = (
        "You are a knowledgeable bibliophile and literary curator with expertise across multiple "
        "genres and fields. Your role is to recommend books that would enrich and expand upon "
        "the themes, ideas, and questions present in the journal entry. Consider both classic "
        "and contemporary works, and include fiction and non-fiction recommendations where appropriate. "
        "For each book, explain specifically how it connects to the journal's content and what "
        "unique perspective it might offer."
    )
    user_prompt = f"""Here is today's journal entry:

{journal_text}

Please provide 4-6 book recommendations based on the themes, questions, and topics present in this journal entry. For each book, include:
1. Title and author
2. A brief description of the book
3. Specific explanation of why this book would be valuable given the journal's content
4. What new perspectives or insights this book might offer

Mix both classic and contemporary works, and consider both fiction and non-fiction where appropriate."""

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content

def send_email(subject, essay_ideas, book_recommendations, to_email, from_email, password):
    """Send an email with the generated content."""
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

        # Format content with HTML
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c5282;">Essay Ideas</h2>
                    <div style="margin-bottom: 30px;">
                        {essay_ideas.replace('\n\n', '</p><p>').replace('\n', '<br>')}
                    </div>
                    
                    <h2 style="color: #2c5282;">Recommended Reading</h2>
                    <div style="margin-bottom: 30px;">
                        {book_recommendations.replace('\n\n', '</p><p>').replace('\n', '<br>')}
                    </div>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html_content, 'html'))

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
        journal_folder_path = find_journal_folder(daily_folder_path)

        # Fetch today's journal entry
        journal_text = fetch_today_journal_entry(journal_folder_path)

        # Generate separate recommendations
        essay_ideas = get_essay_ideas_from_openai(journal_text)
        book_recommendations = get_book_recommendations(journal_text)

        # Current date in mm/dd/yyyy format
        current_date = datetime.now().strftime("%m/%d/%Y")

        # Send the email
        send_email(
            subject=f"Essay Ideas & Reading List ({current_date})",
            essay_ideas=essay_ideas,
            book_recommendations=book_recommendations,
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
