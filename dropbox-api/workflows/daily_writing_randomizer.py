import os
import dropbox
import redis
import random
from datetime import datetime
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Load environment variables
load_dotenv()

# Redis configuration
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

# Configuration  
NUM_FILES_TO_SEND = 5
OBSIDIAN_VAULT_NAME = os.getenv('OBSIDIAN_VAULT_NAME', 'SecondBrain')  # Default vault name

def get_dropbox_access_token():
    """Get Dropbox access token from Redis"""
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

def find_writing_folder(dbx, vault_path):
    """Find folder containing '_Writing' in the vault path"""
    try:
        print(f"Looking for _Writing folder in: {vault_path}")
        response = dbx.files_list_folder(vault_path)
        
        # Process current batch of entries
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                if '_Writing' in entry.name:
                    print(f"Found writing folder: {entry.name} at {entry.path_lower}")
                    return entry.path_lower
        
        # Handle pagination if there are more entries
        while response.has_more:
            response = dbx.files_list_folder_continue(response.cursor)
            for entry in response.entries:
                if isinstance(entry, dropbox.files.FolderMetadata):
                    if '_Writing' in entry.name:
                        print(f"Found writing folder: {entry.name} at {entry.path_lower}")
                        return entry.path_lower
                        
    except dropbox.exceptions.ApiError as e:
        print(f"Error accessing vault folder: {e}")
        raise
    
    raise FileNotFoundError("No folder containing '_Writing' found in the vault path")

def get_all_writing_files(dbx, writing_folder_path, vault_root_path):
    """Get all markdown files from the writing folder and ALL subdirectories"""
    files = []
    try:
        print(f"Getting all files recursively from: {writing_folder_path}")
        response = dbx.files_list_folder(writing_folder_path, recursive=True)
        
        # Process current batch of entries
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.endswith('.md'):
                # Calculate relative path for Obsidian links
                relative_path = entry.path_lower.replace(vault_root_path.lower(), '').lstrip('/')
                
                files.append({
                    'name': entry.name,
                    'path': entry.path_lower,
                    'relative_path': relative_path,
                    'size': entry.size,
                    'modified': entry.server_modified.isoformat()
                })
        
        # Handle pagination if there are more entries - CRITICAL for large folders!
        while response.has_more:
            print(f"Fetching more entries... (current count: {len(files)})")
            response = dbx.files_list_folder_continue(response.cursor)
            for entry in response.entries:
                if isinstance(entry, dropbox.files.FileMetadata) and entry.name.endswith('.md'):
                    # Calculate relative path for Obsidian links
                    relative_path = entry.path_lower.replace(vault_root_path.lower(), '').lstrip('/')
                    
                    files.append({
                        'name': entry.name,
                        'path': entry.path_lower,
                        'relative_path': relative_path,
                        'size': entry.size,
                        'modified': entry.server_modified.isoformat()
                    })
                    
    except dropbox.exceptions.ApiError as e:
        print(f"Error getting files from writing folder: {e}")
        raise
    
    print(f"Found {len(files)} markdown files across all subdirectories")
    return files

def select_random_files(all_files, num_files):
    """Select random files (unique within each day, but no long-term tracking)"""
    if len(all_files) <= num_files:
        print(f"Selecting all {len(all_files)} available files")
        return all_files
    
    selected_files = random.sample(all_files, num_files)
    print(f"Selected {len(selected_files)} random files out of {len(all_files)} total")
    return selected_files

def get_file_content(dbx, file_path):
    """Download and return the content of a file"""
    try:
        metadata, response = dbx.files_download(file_path)
        content = response.content.decode('utf-8')
        return content
    except dropbox.exceptions.ApiError as e:
        print(f"Error downloading file {file_path}: {e}")
        return None

def get_dropbox_share_link(dbx, file_path):
    """Get a shareable Dropbox link for the file"""
    try:
        # Try to get existing shared link first
        try:
            links = dbx.sharing_list_shared_links(path=file_path, direct_only=True)
            if links.links:
                return links.links[0].url
        except:
            pass
        
        # Create new shared link if none exists
        link = dbx.sharing_create_shared_link_with_settings(file_path)
        return link.url
    except dropbox.exceptions.ApiError as e:
        print(f"Warning: Could not create Dropbox share link for {file_path}: {e}")
        return None

def create_obsidian_link(vault_name, relative_path):
    """Create an Obsidian deep link URL"""
    # Remove .md extension for Obsidian links
    clean_path = relative_path.replace('.md', '')
    # URL encode the path
    import urllib.parse
    encoded_path = urllib.parse.quote(clean_path)
    return f"obsidian://open?vault={urllib.parse.quote(vault_name)}&file={encoded_path}"

def send_email(selected_files, file_contents, file_links, to_email, from_email, password):
    """Send an email with the selected writing files"""
    try:
        print("🔄 Connecting to Gmail...")
        s = smtplib.SMTP(host='smtp.gmail.com', port=587)
        s.starttls()
        s.login(from_email, password)

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        
        # Current date for subject
        current_date = datetime.now().strftime("%m/%d/%Y")
        msg['Subject'] = f"Daily Writing Selection ({current_date})"

        # Build email body
        email_body = f"<h2>🎲 Your Daily Writing Selection - {current_date}</h2><br>"
        email_body += f"<p><em>Randomly selected from your writing collection</em></p><hr><br>"
        
        for i, (file_info, content, links) in enumerate(zip(selected_files, file_contents, file_links), 1):
            email_body += f"<h3>{i}. {file_info['name']}</h3>"
            email_body += f"<p><em>📁 {file_info['path']}</em></p>"
            email_body += f"<p><em>📊 {file_info['size']} bytes | 📅 Modified: {file_info['modified']}</em></p>"
            
            # Add action buttons for opening the file
            email_body += "<p style='margin: 10px 0;'>"
            if links['obsidian_link']:
                email_body += f"<a href='{links['obsidian_link']}' style='background-color: #7c3aed; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; margin-right: 10px; display: inline-block;'>📱 Open in Obsidian</a>"
            if links['dropbox_link']:
                email_body += f"<a href='{links['dropbox_link']}' style='background-color: #0061ff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; display: inline-block;'>📦 Open in Dropbox</a>"
            email_body += "</p>"
            
            email_body += f"<div style='background-color: #f9f9f9; padding: 20px; margin: 15px 0; border-left: 4px solid #007acc; border-radius: 5px;'>"
            
            # Convert markdown content to basic HTML formatting
            formatted_content = content.replace('\n\n', '<br><br>').replace('\n', '<br>')
            formatted_content = formatted_content.replace('# ', '<h4>').replace('## ', '<h5>').replace('### ', '<h6>')
            formatted_content = formatted_content.replace('**', '<strong>').replace('*', '<em>')
            
            email_body += formatted_content
            email_body += "</div>"
            
            if i < len(selected_files):
                email_body += "<hr><br>"

        email_body += f"<br><p><em>Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}</em></p>"

        msg.attach(MIMEText(email_body, 'html'))
        s.send_message(msg)
        s.quit()
        print("✅ Email sent successfully!")
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        raise

def main():
    """Main function to select random writing files and email them"""
    try:
        # Get email configuration
        from_email = os.getenv('GMAIL_ACCOUNT')
        password = os.getenv('GMAIL_PASSWORD')
        to_email = from_email  # Send to yourself
        
        if not from_email or not password:
            raise EnvironmentError("Gmail credentials not found in environment variables")
        
        # Initialize Dropbox client
        dbx = dropbox.Dropbox(get_dropbox_access_token())
        
        # Get vault path
        vault_path = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
        if not vault_path:
            raise EnvironmentError("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set.")
        
        print("=" * 60)
        print("DAILY WRITING RANDOMIZER - 5 FILES")
        print("=" * 60)
        
        # Find the writing folder
        writing_folder = find_writing_folder(dbx, vault_path)
        
        # Get all writing files from ALL subdirectories
        all_files = get_all_writing_files(dbx, writing_folder, vault_path)
        
        if not all_files:
            print("No markdown files found in the writing folder!")
            return
        
        # Select random files
        selected_files = select_random_files(all_files, NUM_FILES_TO_SEND)
        
        print(f"\n📋 Selected Files:")
        for i, file_info in enumerate(selected_files, 1):
            print(f"{i}. {file_info['name']} ({file_info['size']} bytes)")
        
        # Download content and generate links for each selected file
        print(f"\n🔄 Downloading content and generating links for {len(selected_files)} files...")
        file_contents = []
        file_links = []
        
        for file_info in selected_files:
            print(f"   Processing: {file_info['name']}")
            
            # Download content
            content = get_file_content(dbx, file_info['path'])
            if content:
                file_contents.append(content)
                print(f"   ✅ Downloaded ({len(content)} characters)")
            else:
                file_contents.append("❌ Error downloading this file")
                print(f"   ❌ Failed to download content")
            
            # Generate links
            print(f"   🔗 Generating links...")
            dropbox_link = get_dropbox_share_link(dbx, file_info['path'])
            obsidian_link = create_obsidian_link(OBSIDIAN_VAULT_NAME, file_info['relative_path'])
            
            file_links.append({
                'dropbox_link': dropbox_link,
                'obsidian_link': obsidian_link
            })
            
            if dropbox_link:
                print(f"   ✅ Dropbox link generated")
            else:
                print(f"   ⚠️  Dropbox link failed")
            print(f"   ✅ Obsidian link generated")
        
        # Send email
        print(f"\n📧 Sending email to {to_email}...")
        send_email(selected_files, file_contents, file_links, to_email, from_email, password)
        
        print(f"\n🎉 Successfully sent daily writing selection!")
        print(f"   Files sent: {len(selected_files)}")
        print(f"   Total files available: {len(all_files)}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    main() 