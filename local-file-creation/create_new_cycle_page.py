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

def find_cycles_folder(base_path):
    for item in os.listdir(base_path):
        if item.endswith("_Cycles") and os.path.isdir(os.path.join(base_path, item)):
            return item
    raise FileNotFoundError("Could not find a folder ending with '_Cycles'")

def fetch_last_cycle_number(cycles_path):
    cycle_files = [f for f in os.listdir(cycles_path) if f.startswith("Cycle ") and f.endswith(".md")]
    if not cycle_files:
        return 0
    cycle_numbers = [int(f.split(" ")[1].split(" ")[0]) for f in cycle_files]
    return max(cycle_numbers)

def create_cycle_file(file_path):
    last_cycle_number = fetch_last_cycle_number(file_path)
    new_cycle_number = last_cycle_number + 1

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
    file_name = f"Cycle {new_cycle_number} ({formatted_wednesday} - {formatted_tuesday}).md"
    full_file_path = os.path.join(file_path, file_name)

    # Check if the file already exists
    if os.path.exists(full_file_path):
        print(f"File '{file_name}' already exists. Skipping creation.")
        return

    # Create the file with content
    try:
        with open(full_file_path, 'w') as file:
            file.write(f"Cycle Start Date: {next_wednesday.strftime('%Y-%m-%d')}\n")
            file.write(f"Cycle End Date: {following_tuesday.strftime('%Y-%m-%d')}\n")
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
        cycles_folder = find_cycles_folder(base_path)
        weekly_cycles_path = os.path.join(base_path, cycles_folder, "_Weekly-Cycles")
        if not os.path.exists(weekly_cycles_path):
            raise FileNotFoundError("'_Weekly-Cycles' subfolder not found")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    create_cycle_file(weekly_cycles_path)

if __name__ == "__main__":
    main()
