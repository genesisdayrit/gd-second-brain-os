import os
import dropbox
import redis
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Redis configuration
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

def get_file_content(dbx, path):
    try:
        metadata, response = dbx.files_download(path)
        content = response.content.decode('utf-8')
        return content
    except dropbox.exceptions.ApiError as e:
        print(f"Error downloading file content: {e}")
        return None

def format_file_metadata(dbx, entry):
    if not entry.name.endswith('.md'):
        return None
        
    metadata = {
        'name': entry.name,
        'path_lower': entry.path_lower,
        'id': entry.id,
        'client_modified': entry.client_modified.strftime('%Y-%m-%d %H:%M:%S'),
        'server_modified': entry.server_modified.strftime('%Y-%m-%d %H:%M:%S'),
        'rev': entry.rev,
        'size': entry.size,
        'content_hash': entry.content_hash,
        'is_downloadable': entry.is_downloadable,
        'content': get_file_content(dbx, entry.path_lower)
    }
    return metadata

def get_all_files_with_metadata(dbx, folder_path, limit=1):
    files_found = []
    try:
        directories_to_check = [folder_path]
        
        while directories_to_check and len(files_found) < limit:
            current_folder = directories_to_check.pop(0)
            response = dbx.files_list_folder(current_folder)
            
            for entry in response.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    if entry.name.endswith('.md'):
                        file_metadata = format_file_metadata(dbx, entry)
                        if file_metadata:
                            files_found.append(file_metadata)
                            if len(files_found) >= limit:
                                break
                elif isinstance(entry, dropbox.files.FolderMetadata):
                    directories_to_check.append(entry.path_lower)
            
            while response.has_more and len(files_found) < limit:
                response = dbx.files_list_folder_continue(response.cursor)
                for entry in response.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        if entry.name.endswith('.md'):
                            file_metadata = format_file_metadata(dbx, entry)
                            if file_metadata:
                                files_found.append(file_metadata)
                                if len(files_found) >= limit:
                                    break
                    elif isinstance(entry, dropbox.files.FolderMetadata):
                        directories_to_check.append(entry.path_lower)
                        
        return files_found
    except dropbox.exceptions.ApiError as e:
        print(f"Error retrieving files: {e}")
        raise

def main():
    try:
        # Initialize Dropbox client
        dbx = dropbox.Dropbox(get_dropbox_access_token())
        
        # Get root folder path
        root_folder = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
        if not root_folder:
            raise EnvironmentError("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set.")
        
        print(f"Retrieving markdown files and metadata from root folder: {root_folder}")
        files_with_metadata = get_all_files_with_metadata(dbx, root_folder, limit=1)
        
        # Print results
        print(f"\nFound {len(files_with_metadata)} markdown files:")
        for idx, file_metadata in enumerate(files_with_metadata, 1):
            print(f"\n{idx}. File Details:")
            for key, value in file_metadata.items():
                if key == 'content':
                    print(f"\n   Content:")
                    print("   " + "\n   ".join(value.split('\n')))
                else:
                    print(f"   {key}: {value}")
            
    except EnvironmentError as e:
        print(f"Environment Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
