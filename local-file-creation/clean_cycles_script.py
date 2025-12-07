import os
import sys
import re
from dotenv import load_dotenv

# Get the directory of the script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Get the root directory (parent of the script directory)
root_dir = os.path.dirname(script_dir)

# Load environment variables from the .env file in the root directory
load_dotenv(os.path.join(root_dir, '.env'))

def find_cycles_folder(base_path):
    """Find the folder ending with '_Cycles'"""
    for item in os.listdir(base_path):
        if item.endswith("_Cycles") and os.path.isdir(os.path.join(base_path, item)):
            return item
    raise FileNotFoundError("Could not find a folder ending with '_Cycles'")

def validate_file_format(filename):
    """
    Validate that filename matches one of the expected formats:
    - 6-Week Cycle {number} (YYYY.MM.DD - YYYY.MM.DD).md
    - 2-Week Cooling Period {number} (YYYY.MM.DD - YYYY.MM.DD).md
    
    Returns: (is_valid, error_message)
    """
    # Pattern for 6-Week Cycle: must include number, dates should have zero-padded month and day
    six_week_pattern = r'^6-Week Cycle \d+ \(\d{4}\.\d{2}\.\d{2} - \d{4}\.\d{2}\.\d{2}\)\.md$'
    
    # Pattern for 2-Week Cooling Period: must include number, dates should have zero-padded month and day
    cooling_pattern = r'^2-Week Cooling Period \d+ \(\d{4}\.\d{2}\.\d{2} - \d{4}\.\d{2}\.\d{2}\)\.md$'
    
    if re.match(six_week_pattern, filename):
        return True, None
    elif re.match(cooling_pattern, filename):
        return True, None
    else:
        # Try to identify what's wrong
        if filename.startswith("6-Week Cycle"):
            return False, "6-Week Cycle format issue (must include number and dates should be YYYY.MM.DD with zero-padding)"
        elif filename.startswith("2-Week Cooling Period"):
            return False, "2-Week Cooling Period format issue (must include number and dates should be YYYY.MM.DD with zero-padding)"
        else:
            return False, "Unknown file format"

def main():
    # Get the base path from environment variable
    base_path = os.getenv('OBSIDIAN_VAULT_BASE_PATH')
    if not base_path:
        print("Error: OBSIDIAN_VAULT_BASE_PATH environment variable not set")
        sys.exit(1)

    try:
        # Find the Cycles folder
        cycles_folder = find_cycles_folder(base_path)
        print(f"Found cycles folder: {cycles_folder}")
        
        # Navigate to _6-Week-Cycles subfolder
        six_week_cycles_path = os.path.join(base_path, cycles_folder, "_6-Week-Cycles")
        
        # Verify it exists
        if not os.path.exists(six_week_cycles_path):
            raise FileNotFoundError("'_6-Week-Cycles' subfolder not found")
        
        print(f"Successfully located _6-Week-Cycles folder at: {six_week_cycles_path}")
        
        # List files in the folder
        files = [f for f in os.listdir(six_week_cycles_path) if os.path.isfile(os.path.join(six_week_cycles_path, f))]
        print(f"\nFound {len(files)} files in _6-Week-Cycles:")
        
        # Validate each file
        valid_files = []
        invalid_files = []
        
        for file in sorted(files):
            is_valid, error_msg = validate_file_format(file)
            if is_valid:
                valid_files.append(file)
                print(f"  ✓ {file}")
            else:
                invalid_files.append((file, error_msg))
                print(f"  ✗ {file}")
                print(f"    ERROR: {error_msg}")
        
        # Summary
        print(f"\n{'='*70}")
        print(f"SUMMARY:")
        print(f"  Total files: {len(files)}")
        print(f"  Valid files: {len(valid_files)}")
        print(f"  Invalid files: {len(invalid_files)}")
        
        if invalid_files:
            print(f"\n{'='*70}")
            print("INVALID FILES FOUND:")
            for file, error in invalid_files:
                print(f"  - {file}")
                print(f"    Issue: {error}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

