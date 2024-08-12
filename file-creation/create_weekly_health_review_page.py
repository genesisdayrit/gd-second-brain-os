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

def fetch_last_review_number(review_path):
    review_files = [f for f in os.listdir(review_path) if f.startswith("Weekly Health Review ") and f.endswith(".md")]
    if not review_files:
        return 0
    review_numbers = [int(f.split(" ")[3].split(" ")[0]) for f in review_files]
    return max(review_numbers)

def create_health_review_file(file_path):
    last_review_number = fetch_last_review_number(file_path)
    new_review_number = last_review_number + 1

    # Calculate the next Wednesday
    today = datetime.now()
    days_until_next_wednesday = (2 - today.weekday()) % 7
    if days_until_next_wednesday == 0:
        days_until_next_wednesday = 7
    next_wednesday = today + timedelta(days=days_until_next_wednesday)
    
    following_tuesday = next_wednesday + timedelta(days=6)
    
    formatted_wednesday = next_wednesday.strftime("%b. %d")
    formatted_tuesday = following_tuesday.strftime("%b. %d, %Y")

    # Create the file name
    file_name = f"Weekly Health Review {new_review_number} ({formatted_wednesday} - {formatted_tuesday}).md"
    full_file_path = os.path.join(file_path, file_name)

    # Check if the file already exists
    if os.path.exists(full_file_path):
        print(f"File '{file_name}' already exists. Skipping creation.")
        return

    # Create the file with content
    try:
        with open(full_file_path, 'w') as file:
            file.write(f"# Weekly Health Review {new_review_number} ({formatted_wednesday} - {formatted_tuesday})\n\n")
            file.write(f"Review #: {new_review_number}\n")
            file.write(f"Start Date: {next_wednesday.strftime('%Y-%m-%d')}\n")
            file.write(f"End Date: {following_tuesday.strftime('%Y-%m-%d')}\n")
        print(f"Successfully created file '{file_name}'")
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
        health_review_path = os.path.join(base_path, weekly_folder, "_Weekly-Health-Review")
        if not os.path.exists(health_review_path):
            raise FileNotFoundError("'_Weekly-Health-Review' subfolder not found")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    create_health_review_file(health_review_path)

if __name__ == "__main__":
    main()
