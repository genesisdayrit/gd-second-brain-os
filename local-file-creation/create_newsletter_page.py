import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Get the directory of the script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Get the root directory (parent of the script directory)
root_dir = os.path.dirname(script_dir)

# Load environment variables from the .env file in the root directory
load_dotenv(os.path.join(root_dir, '.env'))

def find_weekly_folder(base_path):
    for item in os.listdir(base_path):
        if item.endswith("_Weekly") and os.path.isdir(os.path.join(base_path, item)):
            return item
    raise FileNotFoundError("Could not find a folder ending with '_Weekly'")

def create_newsletter_file(file_path):
    # Calculate the Sunday after next upcoming Sunday
    today = datetime.now()
    days_until_next_sunday = (6 - today.weekday()) % 7
    if days_until_next_sunday == 0:  # If today is Sunday, set days_until_next_sunday to 7 to get the next Sunday
        days_until_next_sunday = 7
    second_upcoming_sunday = today + timedelta(days=days_until_next_sunday + 7)
    formatted_date = second_upcoming_sunday.strftime("%b. %d, %Y")

    # Create the file name
    file_name = f"Weekly Newsletter {formatted_date}.md"
    full_file_path = os.path.join(file_path, file_name)

    # Check if the file already exists
    if os.path.exists(full_file_path):
        print(f"File '{file_name}' already exists. Skipping creation.")
        return

    # Create an empty file
    try:
        with open(full_file_path, 'w') as file:
            pass  # This creates an empty file
        print(f"Successfully created empty file '{file_name}'")
    except IOError as e:
        print(f"Error creating file: {e}")

def main():
    # Get the base path from environment variable
    base_path = os.getenv('OBSIDIAN_VAULT_BASE_PATH')
    if not base_path:
        print("Error: OBSIDIAN_VAULT_BASE_PATH environment variable not set")
        sys.exit(1)

    try:
        weekly_folder = find_weekly_folder(base_path)
        newsletter_path = os.path.join(base_path, weekly_folder, "_Newsletters")
        if not os.path.exists(newsletter_path):
            raise FileNotFoundError("'_Newsletters' subfolder not found")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    create_newsletter_file(newsletter_path)

if __name__ == "__main__":
    main()