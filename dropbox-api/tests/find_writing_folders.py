import os
import dropbox
import redis
from dotenv import load_dotenv

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

def find_writing_folders(dbx, folder_path):
    """
    Search for folders containing '_Writing' in their names at the parent level only
    """
    writing_folders = []
    
    try:
        print(f"Searching in: {folder_path}")
        response = dbx.files_list_folder(folder_path)
        
        # Process current batch of entries
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                folder_name = entry.name
                folder_path = entry.path_lower
                
                # Check if folder name contains '_Writing'
                if '_Writing' in folder_name:
                    writing_folders.append({
                        'name': folder_name,
                        'path': folder_path,
                        'id': entry.id
                    })
                    print(f"Found writing folder: {folder_name} at {folder_path}")
        
        # Handle pagination if there are more entries
        while response.has_more:
            response = dbx.files_list_folder_continue(response.cursor)
            for entry in response.entries:
                if isinstance(entry, dropbox.files.FolderMetadata):
                    folder_name = entry.name
                    folder_path = entry.path_lower
                    
                    # Check if folder name contains '_Writing'
                    if '_Writing' in folder_name:
                        writing_folders.append({
                            'name': folder_name,
                            'path': folder_path,
                            'id': entry.id
                        })
                        print(f"Found writing folder: {folder_name} at {folder_path}")
                        
    except dropbox.exceptions.ApiError as e:
        print(f"Error accessing folder {folder_path}: {e}")
        raise
    
    return writing_folders

def main():
    try:
        # Initialize Dropbox client
        dbx = dropbox.Dropbox(get_dropbox_access_token())
        
        # Get root folder path
        root_folder = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
        if not root_folder:
            raise EnvironmentError("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set.")
        
        print(f"Searching for folders containing '_Writing' in: {root_folder}")
        print("=" * 60)
        
        # Find writing folders
        writing_folders = find_writing_folders(dbx, root_folder)
        
        # Display results
        print("\n" + "=" * 60)
        print(f"SEARCH COMPLETE - Found {len(writing_folders)} folder(s) containing '_Writing':")
        print("=" * 60)
        
        if writing_folders:
            for idx, folder_info in enumerate(writing_folders, 1):
                print(f"\n{idx}. Folder Name: {folder_info['name']}")
                print(f"   Full Path: {folder_info['path']}")
                print(f"   Folder ID: {folder_info['id']}")
        else:
            print("\nNo folders containing '_Writing' were found.")
            
    except EnvironmentError as e:
        print(f"Environment Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main() 