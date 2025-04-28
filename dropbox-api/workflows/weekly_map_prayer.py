import os
import dropbox
import redis
from dotenv import load_dotenv
from datetime import datetime, timedelta
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

# OpenAI API Key
openai_api_key = os.getenv('OPENAI_API_KEY')

def get_dropbox_access_token():
    """Retrieve Dropbox access token from Redis."""
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Dropbox Client Initialization
def initialize_dropbox_client():
    """Initialize and return a Dropbox client."""
    dropbox_access_token = get_dropbox_access_token()
    return dropbox.Dropbox(dropbox_access_token)

def find_weekly_folder(dbx, vault_path):
    """Search for the '_Weekly' folder in the specified vault path."""
    response = dbx.files_list_folder(vault_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Weekly' in Dropbox")

def find_weekly_maps_folder(dbx, weekly_folder_path):
    """Search for the '_Weekly-Maps' folder inside the '_Weekly' folder."""
    response = dbx.files_list_folder(weekly_folder_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith("_Weekly-Maps"):
            return entry.path_lower
    raise FileNotFoundError("Could not find a folder ending with '_Weekly-Maps' in Dropbox")

def get_current_week_sunday_date():
    """Calculate the date of the current week's Sunday (or today if it is Sunday)."""
    today = datetime.now()
    # If today is Sunday (6), return today's date
    if today.weekday() == 6:
        return today.strftime("%Y-%m-%d")
    # Otherwise, calculate the next Sunday
    days_until_sunday = (6 - today.weekday()) % 7
    next_sunday = today + timedelta(days=days_until_sunday)
    return next_sunday.strftime("%Y-%m-%d")

def find_weekly_map_file(dbx, weekly_maps_folder_path, target_date):
    """Find the weekly map file for the specified date."""
    response = dbx.files_list_folder(weekly_maps_folder_path)
    target_filename_part = f"weekly map {target_date}".lower()
    
    all_files = []
    # Get all files, handling pagination
    while True:
        all_files.extend(response.entries)
        if not response.has_more:
            break
        response = dbx.files_list_folder_continue(response.cursor)
    
    # Look for the file with the target date in its name
    for file in all_files:
        if isinstance(file, dropbox.files.FileMetadata) and target_filename_part in file.name.lower():
            return file
            
    return None

def get_weekly_map_content(dbx, file_metadata):
    """Download and return the content of the weekly map file."""
    _, response = dbx.files_download(file_metadata.path_lower)
    return response.content.decode('utf-8')

def generate_prayer(weekly_map_content):
    """Generate a prayer based on the weekly map content using OpenAI GPT-4o-mini."""
    client = OpenAI(api_key=openai_api_key)
    system_prompt = (
        "You are a thoughtful, faithful spiritual guide who composes heartfelt, personalized prayers. "
        "Your prayers should be respectful, uplifting, and relevant to the person's weekly goals and aspirations. "
        "Feel free to make explicit references to God in your prayer, using reverent and traditional prayer language."
    )
    user_prompt = (
        "Based on my weekly plan and goals below, please compose a meaningful prayer that: "
        "1. Acknowledges the week ahead and its challenges "
        "2. Asks God for guidance, strength, and clarity "
        "3. Expresses gratitude to God for opportunities to grow "
        "4. Concludes with hope and divine purpose "
        "Keep the prayer between 8-12 sentences, and make it sincere, personal, and uplifting. "
        "Please use appropriate references to God throughout the prayer.\n\n"
        f"Here is my weekly plan:\n{weekly_map_content}"
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return completion.choices[0].message.content

def send_email(subject, prayer, weekly_map_content, to_email, from_email, password):
    """Send an email with the generated prayer and weekly map content."""
    try:
        s = smtplib.SMTP(host='smtp.gmail.com', port=587)
        s.starttls()
        s.login(from_email, password)

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject

        prayer_html = f"<h2>Weekly Prayer</h2>{prayer.replace('\n', '<br>')}"
        weekly_map_html = f"<h3>Weekly Map Content</h3><pre>{weekly_map_content}</pre>"

        message_body = f"{prayer_html}<br><hr><br>{weekly_map_html}"
        msg.attach(MIMEText(message_body, 'html'))

        s.send_message(msg)
        s.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Error occurred while sending email: {e}")

def main():
    try:
        # Get Dropbox vault path from environment variables
        dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
        if not dropbox_vault_path:
            raise EnvironmentError("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        
        # Initialize Dropbox client
        dbx = initialize_dropbox_client()
        
        # Find the _Weekly folder
        weekly_folder_path = find_weekly_folder(dbx, dropbox_vault_path)
        print(f"Found _Weekly folder at: {weekly_folder_path}")
        
        # Find the _Weekly-Maps folder
        weekly_maps_folder_path = find_weekly_maps_folder(dbx, weekly_folder_path)
        print(f"Found _Weekly-Maps folder at: {weekly_maps_folder_path}")
        
        # Get the current week's Sunday date
        target_date = get_current_week_sunday_date()
        print(f"Looking for weekly map for the week ending: {target_date}")
        
        # Find the weekly map file for the current week
        weekly_map_file = find_weekly_map_file(dbx, weekly_maps_folder_path, target_date)
        
        if weekly_map_file:
            print(f"Found weekly map: {weekly_map_file.name}")
            
            # Get the content of the weekly map file
            weekly_map_content = get_weekly_map_content(dbx, weekly_map_file)
            print("Retrieved weekly map content")
            
            # Generate prayer based on weekly map content
            print("Generating prayer...")
            prayer = generate_prayer(weekly_map_content)
            print("Prayer generated")
            
            # Get email configuration from environment variables
            from_email = os.getenv('GMAIL_ACCOUNT')
            password = os.getenv('GMAIL_PASSWORD')
            to_email = from_email  # or another recipient
            
            if not from_email or not password:
                raise EnvironmentError("Email credentials not found in environment variables")
            
            # Format the date
            formatted_date = datetime.now().strftime("%m/%d/%Y")
            
            # Send email
            print("Sending email...")
            send_email(
                subject=f"Weekly Prayer & Reflection ({formatted_date})",
                prayer=prayer,
                weekly_map_content=weekly_map_content,
                to_email=to_email,
                from_email=from_email,
                password=password
            )
            
            return prayer
        else:
            print(f"No weekly map found for the week ending {target_date}")
            return None
            
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    main() 