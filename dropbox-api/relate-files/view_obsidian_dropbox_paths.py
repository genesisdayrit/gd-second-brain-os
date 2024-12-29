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

# Function to get the Dropbox access token from Redis
def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token

# Initialize Dropbox client using token from Redis
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# Function to recursively retrieve all directory paths in the specified Dropbox folder
def get_all_directory_paths(folder_path, output_file):
    try:
        with open(output_file, 'w') as file:
            directories_to_check = [folder_path]

            while directories_to_check:
                current_folder = directories_to_check.pop(0)
                response = dbx.files_list_folder(current_folder)

                for entry in response.entries:
                    if isinstance(entry, dropbox.files.FolderMetadata):
                        file.write(entry.path_lower + '\n')
                        directories_to_check.append(entry.path_lower)

                while response.has_more:
                    response = dbx.files_list_folder_continue(response.cursor)
                    for entry in response.entries:
                        if isinstance(entry, dropbox.files.FolderMetadata):
                            file.write(entry.path_lower + '\n')
                            directories_to_check.append(entry.path_lower)

        print(f"All directory paths have been written to {output_file}")

    except dropbox.exceptions.ApiError as e:
        print(f"Error retrieving directory paths: {e}")
        raise

# Main function
def main():
    try:
        # Use the OBSIDIAN_VAULT_PATH from environment variables
        root_folder = os.getenv("DROPBOX_OBSIDIAN_VAULT_PATH")
        if not root_folder:
            raise EnvironmentError("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable is not set.")

        output_file = "obsidian_directory_paths.txt"

        print(f"Retrieving all directory paths starting from root folder: {root_folder}")
        get_all_directory_paths(root_folder, output_file)
    except EnvironmentError as e:
        print(f"Environment Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
