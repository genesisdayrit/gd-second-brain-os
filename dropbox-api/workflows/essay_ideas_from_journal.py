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
import logging

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Timezone Configuration ---
timezone_str = os.getenv("SYSTEM_TIMEZONE", "US/Eastern")
logger.info(f"Using timezone: {timezone_str}")

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
    Fetch yesterday's journal entry from the '_Journal' folder, assuming lowercase file names.
    """
    # Set up timezones
    system_tz = timezone(timezone_str)
    utc = timezone('UTC')

    # Current time in system timezone and UTC
    now_system = datetime.now(system_tz)
    # Subtract one day to get yesterday's date
    yesterday = now_system - timedelta(days=1)
    yesterday_date = yesterday.strftime("%b %-d, %Y").lower()

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

    # Search for yesterday's file
    for entry in all_files:
        file_name = entry.name.strip().lower()  # Ensure lowercase
        if file_name == f"{yesterday_date}.md":  # Match yesterday's file
            # Download and return the file contents
            metadata, response = dbx.files_download(entry.path_lower)
            return response.content.decode('utf-8')

    # Raise an error if no match is found
    raise FileNotFoundError(f"Yesterday's journal entry ({yesterday_date}) not found in the '_Journal' folder.")

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

def get_supporting_materials_with_web_search(journal_text, essay_ideas):
    """Generate supporting materials (essays, articles, books) using OpenAI web search based on journal content and essay ideas."""
    client = OpenAI(api_key=openai_api_key)
    
    # Create a comprehensive prompt that includes both journal content and essay ideas
    search_prompt = f"""Based on the following journal entry and essay ideas, please search the web for relevant supporting materials including recent articles, essays, books, and other resources that would help develop these topics further.

JOURNAL ENTRY:
{journal_text}

ESSAY IDEAS:
{essay_ideas}

Please search for and provide:
1. Recent articles or essays from reputable publications that relate to these themes
2. Relevant books (both recent and classic) that would provide deeper insight
3. Academic papers or research that supports these topics
4. Any other valuable resources (documentaries, podcasts, etc.)

For each resource, please include:
- **Title and author/source**
- Brief description of how it relates to the journal themes and essay ideas
- Key insights or perspectives it offers
- Publication date when available

Important: Please provide proper citations and web sources for all recommendations. Use web search to find current, relevant materials rather than relying on training data. Format your response using markdown with **bold** for titles and proper [link text](url) formatting where applicable.

Focus on finding high-quality, credible sources that would genuinely help develop the essay ideas further."""

    completion = client.chat.completions.create(
        model="gpt-4o-search-preview",
        web_search_options={
            "search_context_size": "medium"
        },
        messages=[
            {
                "role": "user",
                "content": search_prompt
            }
        ]
    )
    
    content = completion.choices[0].message.content
    citations = completion.choices[0].message.annotations if hasattr(completion.choices[0].message, 'annotations') and completion.choices[0].message.annotations else []
    
    logger.info(f"Web search completed successfully with {len(citations)} citations")
    return content, citations

def markdown_to_html(text):
    """Convert markdown formatting to HTML."""
    import re
    
    # Convert **bold** to <strong>bold</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # Convert [link text](url) to <a href="url">link text</a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)
    
    # Convert ### Headers to <h3>
    text = re.sub(r'^### (.*?)$', r'<h3 style="color: #2c5282; margin-top: 20px; margin-bottom: 10px;">\1</h3>', text, flags=re.MULTILINE)
    
    # Convert ## Headers to <h3> (treating as subheaders)
    text = re.sub(r'^## (.*?)$', r'<h3 style="color: #2c5282; margin-top: 20px; margin-bottom: 10px;">\1</h3>', text, flags=re.MULTILINE)
    
    # Convert # Headers to <h2>
    text = re.sub(r'^# (.*?)$', r'<h2 style="color: #2c5282; margin-top: 25px; margin-bottom: 15px;">\1</h2>', text, flags=re.MULTILINE)
    
    # Convert bullet points (- item) to proper list items
    lines = text.split('\n')
    in_list = False
    result_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                result_lines.append('<ul style="margin: 10px 0; padding-left: 20px;">')
                in_list = True
            result_lines.append(f'<li style="margin: 5px 0;">{stripped[2:]}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append(line)
    
    if in_list:
        result_lines.append('</ul>')
    
    text = '\n'.join(result_lines)
    
    # Convert double line breaks to paragraph breaks
    text = re.sub(r'\n\n+', '</p><p style="margin: 15px 0; line-height: 1.6;">', text)
    
    # Wrap in paragraph tags if not already wrapped
    if not text.startswith('<'):
        text = f'<p style="margin: 15px 0; line-height: 1.6;">{text}</p>'
    
    return text

def send_email(subject, essay_ideas, supporting_materials, citations, to_email, from_email, password):
    """Send an email with the generated content and citations."""
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

        # Format citations as HTML links
        citations_html = ""
        if citations:
            citations_html = "<div style='margin-top: 30px; padding: 20px; background-color: #f8f9fa; border-left: 4px solid #2c5282; border-radius: 5px;'>"
            citations_html += "<h3 style='color: #2c5282; margin-top: 0; margin-bottom: 15px;'>📚 Sources & Citations</h3>"
            citations_html += "<ul style='margin: 0; padding-left: 20px; list-style-type: none;'>"
            for i, citation in enumerate(citations, 1):
                try:
                    if hasattr(citation, 'type') and citation.type == 'url_citation':
                        if hasattr(citation, 'url_citation'):
                            url_info = citation.url_citation
                            citations_html += f"<li style='margin: 8px 0; padding: 5px 0; border-bottom: 1px solid #e9ecef;'><strong>{i}.</strong> <a href='{url_info.url}' target='_blank' style='color: #2c5282; text-decoration: none;'>{url_info.title}</a></li>"
                    elif hasattr(citation, 'url') and hasattr(citation, 'title'):
                        citations_html += f"<li style='margin: 8px 0; padding: 5px 0; border-bottom: 1px solid #e9ecef;'><strong>{i}.</strong> <a href='{citation.url}' target='_blank' style='color: #2c5282; text-decoration: none;'>{citation.title}</a></li>"
                except Exception as cite_error:
                    logger.warning(f"Error processing citation: {cite_error}")
                    citations_html += f"<li style='margin: 8px 0; padding: 5px 0;'><strong>{i}.</strong> Citation available (formatting error)</li>"
            citations_html += "</ul></div>"

        # Convert markdown to HTML for both sections
        essay_ideas_html = markdown_to_html(essay_ideas)
        supporting_materials_html = markdown_to_html(supporting_materials)

        # Format content with improved HTML
        html_content = f"""
        <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 700px; margin: 0 auto; padding: 30px; background-color: #ffffff; }}
                    .section {{ margin-bottom: 40px; }}
                    .header {{ color: #2c5282; border-bottom: 3px solid #e9ecef; padding-bottom: 10px; margin-bottom: 25px; }}
                    a {{ color: #2c5282; }}
                    a:hover {{ color: #1a365d; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="section">
                        <h1 class="header">💡 Essay Ideas</h1>
                        <div>
                            {essay_ideas_html}
                        </div>
                    </div>
                    
                    <div class="section">
                        <h1 class="header">📖 Supporting Materials</h1>
                        <div>
                            {supporting_materials_html}
                        </div>
                    </div>
                    
                    {citations_html}
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html_content, 'html'))

        # Send the message via the server
        s.send_message(msg)
        s.quit()
        logger.info("Email sent successfully")
    except Exception as e:
        logger.error(f"Error occurred while sending email: {e}")

def main():
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    from_email = os.getenv('GMAIL_ACCOUNT')
    password = os.getenv('GMAIL_PASSWORD')
    to_email = from_email  # or another recipient

    if not dropbox_vault_path:
        logger.error("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        return
    
    try:
        # Locate folders
        daily_folder_path = find_daily_folder(dropbox_vault_path)
        journal_folder_path = find_journal_folder(daily_folder_path)

        # Fetch today's journal entry
        journal_text = fetch_today_journal_entry(journal_folder_path)
        logger.info("Successfully fetched today's journal entry")

        # Generate essay ideas
        essay_ideas = get_essay_ideas_from_openai(journal_text)
        logger.info("Successfully generated essay ideas")

        # Get supporting materials using web search
        supporting_materials, citations = get_supporting_materials_with_web_search(journal_text, essay_ideas)
        logger.info(f"Successfully found supporting materials with {len(citations)} citations")

        # Current date in mm/dd/yyyy format
        current_date = datetime.now().strftime("%m/%d/%Y")

        # Send the email
        send_email(
            subject=f"Essay Ideas & Supporting Materials ({current_date})",
            essay_ideas=essay_ideas,
            supporting_materials=supporting_materials,
            citations=citations,
            to_email=to_email,
            from_email=from_email,
            password=password
        )
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
