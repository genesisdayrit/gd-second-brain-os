import os
import sys
import redis
import dropbox
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
try:
    r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)
    r.ping()  # Test connection
    print("Connected to Redis successfully.")
except redis.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
    sys.exit(1)

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
print("Connected to Dropbox successfully.")

def display_cycle_variables():
    """Display all cycle-related variables from Redis"""
    print("\nCurrent cycle variables in Redis:")
    print("="*40)
    
    # Two-week cooling period variables
    cooling_vars = [
        'two_week_cooling_period_start_date',
        'two_week_cooling_period_end_date',
        'next_two_week_cooling_period_start_date',
        'next_two_week_cooling_period_end_date'
    ]
    
    # Six-week cycle variables
    cycle_vars = [
        '6_week_cycle_start_date',
        '6_week_cycle_end_date',
        'next_6_week_cycle_start_date',
        'next_6_week_cycle_end_date'
    ]
    
    # Display two-week cooling period variables
    print("Two-week cooling period:")
    for var in cooling_vars:
        value = r.get(var)
        print(f"  {var}: {value}")
    
    # Display six-week cycle variables
    print("\nSix-week cycle:")
    for var in cycle_vars:
        value = r.get(var)
        print(f"  {var}: {value}")
    
    print("="*40)

def calculate_two_week_cooling_periods(start_date):
    """Calculate all dates related to the two-week cooling period."""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    
    # Calculate end date (start + 13 days = 14 day period)
    end = start + timedelta(days=13)
    
    # Calculate next cycle (start + 8 weeks)
    next_start = start + timedelta(weeks=8)
    next_end = next_start + timedelta(days=13)
    
    return {
        'two_week_cooling_period_start_date': start_date,
        'two_week_cooling_period_end_date': end.strftime('%Y-%m-%d'),
        'next_two_week_cooling_period_start_date': next_start.strftime('%Y-%m-%d'),
        'next_two_week_cooling_period_end_date': next_end.strftime('%Y-%m-%d')
    }

def calculate_six_week_cycles(start_date):
    """Calculate all dates related to the six-week cycle."""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    
    # Calculate end date (start + (7*6-1) days)
    end = start + timedelta(days=(7*6-1))
    
    # Calculate next cycle (end date + 15 days for cooling period)
    next_start = end + timedelta(days=15)
    next_end = next_start + timedelta(days=(7*6-1))
    
    return {
        '6_week_cycle_start_date': start_date,
        '6_week_cycle_end_date': end.strftime('%Y-%m-%d'),
        'next_6_week_cycle_start_date': next_start.strftime('%Y-%m-%d'),
        'next_6_week_cycle_end_date': next_end.strftime('%Y-%m-%d')
    }

def is_date_between(check_date, start_date, end_date):
    """Check if a date falls between start and end dates (inclusive)."""
    return start_date <= check_date <= end_date

def update_redis_dates(date_dict):
    """Update multiple Redis keys with their corresponding values."""
    for key, value in date_dict.items():
        r.set(key, value)
        print(f"Updated {key}: {value}")

def resolve_cycle_dates():
    """Resolve any issues with cycle dates in Redis."""
    print("Resolving cycle dates...")
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    today_date = datetime.strptime(today, '%Y-%m-%d')
    
    # Get current values from Redis
    cooling_start = r.get('two_week_cooling_period_start_date')
    cooling_end = r.get('two_week_cooling_period_end_date')
    cycle_start = r.get('6_week_cycle_start_date')
    cycle_end = r.get('6_week_cycle_end_date')
    
    # Check if values exist in Redis
    if not cooling_start or not cooling_end or not cycle_start or not cycle_end:
        print("Error: One or more required dates not found in Redis.")
        print("Please run the update_long_cycle_start_dates.py script to set up cycle dates.")
        sys.exit(1)
    
    # Convert string dates to datetime objects
    cooling_start_date = datetime.strptime(cooling_start, '%Y-%m-%d')
    cooling_end_date = datetime.strptime(cooling_end, '%Y-%m-%d')
    cycle_start_date = datetime.strptime(cycle_start, '%Y-%m-%d')
    cycle_end_date = datetime.strptime(cycle_end, '%Y-%m-%d')
    
    # Print current date information
    print(f"Current date: {today}")
    print(f"Current 2-week cooling period: {cooling_start} to {cooling_end}")
    print(f"Current 6-week cycle: {cycle_start} to {cycle_end}")
    
    # Check which period we're in
    in_cooling_period = is_date_between(today_date, cooling_start_date, cooling_end_date)
    in_six_week_cycle = is_date_between(today_date, cycle_start_date, cycle_end_date)
    
    print(f"Are we in the cooling period? {in_cooling_period}")
    print(f"Are we in the 6-week cycle? {in_six_week_cycle}")
    
    # Handle the case where we're in cooling period and 6-week cycle has ended
    if in_cooling_period and cycle_end_date < today_date:
        print(f"Currently in the 2-week cooling period and the 6-week cycle has ended.")
        
        # Set new 6-week cycle start date to day after cooling period ends
        new_cycle_start = (cooling_end_date + timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"Adjusting 6-week cycle to start on {new_cycle_start} (after current cooling period ends)")
        
        # Calculate new dates for 6-week cycle
        new_cycle_dates = calculate_six_week_cycles(new_cycle_start)
        
        # Update Redis with new dates
        update_redis_dates(new_cycle_dates)
        return True
        
    # Handle the case where we're in 6-week cycle and cooling period has ended
    elif in_six_week_cycle and cooling_end_date < today_date:
        print(f"Currently in the 6-week cycle and the cooling period has ended.")
        
        # Set new cooling period start date to day after 6-week cycle ends
        new_cooling_start = (cycle_end_date + timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"Adjusting cooling period to start on {new_cooling_start} (after current 6-week cycle ends)")
        
        # Calculate new dates for cooling period
        new_cooling_dates = calculate_two_week_cooling_periods(new_cooling_start)
        
        # Update Redis with new dates
        update_redis_dates(new_cooling_dates)
        return True
    
    # Check for actual overlap (one period starts during another)
    elif in_cooling_period or in_six_week_cycle:
        cooling_overlaps_cycle = (
            (cooling_start_date <= cycle_start_date <= cooling_end_date) or 
            (cooling_start_date <= cycle_end_date <= cooling_end_date)
        )
        
        cycle_overlaps_cooling = (
            (cycle_start_date <= cooling_start_date <= cycle_end_date) or 
            (cycle_start_date <= cooling_end_date <= cycle_end_date)
        )
        
        if in_cooling_period and (cooling_overlaps_cycle or cycle_overlaps_cooling):
            print(f"Currently in the 2-week cooling period ({cooling_start} to {cooling_end})")
            print("Overlap detected: 6-week cycle would overlap with cooling period.")
            
            # Set new 6-week cycle start date to day after cooling period ends
            new_cycle_start = (cooling_end_date + timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"Adjusting 6-week cycle to start on {new_cycle_start} (after cooling period ends)")
            
            # Calculate new dates for 6-week cycle
            new_cycle_dates = calculate_six_week_cycles(new_cycle_start)
            
            # Update Redis with new dates
            update_redis_dates(new_cycle_dates)
            return True
            
        elif in_six_week_cycle and (cooling_overlaps_cycle or cycle_overlaps_cooling):
            print(f"Currently in the 6-week cycle ({cycle_start} to {cycle_end})")
            print("Overlap detected: 2-week cooling period would overlap with 6-week cycle.")
            
            # Set new cooling period start date to day after 6-week cycle ends
            new_cooling_start = (cycle_end_date + timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"Adjusting 2-week cooling period to start on {new_cooling_start} (after 6-week cycle ends)")
            
            # Calculate new dates for 2-week cooling period
            new_cooling_dates = calculate_two_week_cooling_periods(new_cooling_start)
            
            # Update Redis with new dates
            update_redis_dates(new_cooling_dates)
            return True
        else:
            print("No overlaps detected with current cycles.")
    else:
        print("Not currently in either the 2-week cooling period or the 6-week cycle.")
        
        # Both periods have ended, need to decide which to update
        if cooling_end_date < today_date and cycle_end_date < today_date:
            print("Both periods have already ended.")
            
            # Find which one ended most recently
            if cooling_end_date > cycle_end_date:
                print(f"The 2-week cooling period ended most recently on {cooling_end}")
                
                # Set new 6-week cycle to start after the most recent cooling period
                new_cycle_start = (cooling_end_date + timedelta(days=1)).strftime('%Y-%m-%d')
                
                # If that date is in the past, set it to tomorrow
                if datetime.strptime(new_cycle_start, '%Y-%m-%d') < today_date:
                    new_cycle_start = (today_date + timedelta(days=1)).strftime('%Y-%m-%d')
                    
                print(f"Adjusting 6-week cycle to start on {new_cycle_start}")
                
                # Calculate new dates for 6-week cycle
                new_cycle_dates = calculate_six_week_cycles(new_cycle_start)
                
                # Update Redis with new dates
                update_redis_dates(new_cycle_dates)
                return True
            else:
                print(f"The 6-week cycle ended most recently on {cycle_end}")
                
                # Set new cooling period to start after the most recent 6-week cycle
                new_cooling_start = (cycle_end_date + timedelta(days=1)).strftime('%Y-%m-%d')
                
                # If that date is in the past, set it to tomorrow
                if datetime.strptime(new_cooling_start, '%Y-%m-%d') < today_date:
                    new_cooling_start = (today_date + timedelta(days=1)).strftime('%Y-%m-%d')
                    
                print(f"Adjusting 2-week cooling period to start on {new_cooling_start}")
                
                # Calculate new dates for cooling period
                new_cooling_dates = calculate_two_week_cooling_periods(new_cooling_start)
                
                # Update Redis with new dates
                update_redis_dates(new_cooling_dates)
                return True
        
    return False  # No changes made to Redis

def find_cycles_folder(vault_path):
    """Find the folder with '_Cycles' in the name in Dropbox"""
    try:
        response = dbx.files_list_folder(vault_path)
        for entry in response.entries:
            if isinstance(entry, dropbox.files.FolderMetadata) and '_Cycles' in entry.name:
                return entry.path_lower
        raise FileNotFoundError("Could not find a folder containing '_Cycles' in the name in Dropbox")
    except dropbox.exceptions.ApiError as e:
        print(f"Dropbox API error while searching for cycles folder: {e}")
        raise

def ensure_six_week_cycles_folder(cycles_path):
    """Make sure the _6-Week-Cycles folder exists in Dropbox, create if not"""
    six_week_cycles_path = f"{cycles_path}/_6-Week-Cycles"
    
    try:
        # Check if folder exists
        dbx.files_get_metadata(six_week_cycles_path)
        print(f"'_6-Week-Cycles' folder found at {six_week_cycles_path}")
    except dropbox.exceptions.ApiError as e:
        if isinstance(e.error, dropbox.files.GetMetadataError):
            print(f"'_6-Week-Cycles' folder not found. Creating it now.")
            try:
                dbx.files_create_folder_v2(six_week_cycles_path)
                print(f"Created '_6-Week-Cycles' folder at {six_week_cycles_path}")
            except dropbox.exceptions.ApiError as create_error:
                print(f"Error creating '_6-Week-Cycles' folder: {create_error}")
                raise
        else:
            print(f"Dropbox API error: {e}")
            raise
    
    return six_week_cycles_path

def format_date_for_filename(date_str):
    """Convert date from YYYY-MM-DD to YYYY.MM.DD format for filenames"""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    return date_obj.strftime('%Y.%m.%d')

def create_cycle_files(weekly_cycles_path):
    """Create Markdown files for each cycle period in Dropbox"""
    # Get cycle dates from Redis
    current_cooling_start = r.get('two_week_cooling_period_start_date')
    current_cooling_end = r.get('two_week_cooling_period_end_date')
    next_cooling_start = r.get('next_two_week_cooling_period_start_date')
    next_cooling_end = r.get('next_two_week_cooling_period_end_date')
    
    current_cycle_start = r.get('6_week_cycle_start_date')
    current_cycle_end = r.get('6_week_cycle_end_date')
    next_cycle_start = r.get('next_6_week_cycle_start_date')
    next_cycle_end = r.get('next_6_week_cycle_end_date')
    
    # Format dates for filenames
    current_cooling_start_fmt = format_date_for_filename(current_cooling_start)
    current_cooling_end_fmt = format_date_for_filename(current_cooling_end)
    next_cooling_start_fmt = format_date_for_filename(next_cooling_start)
    next_cooling_end_fmt = format_date_for_filename(next_cooling_end)
    
    current_cycle_start_fmt = format_date_for_filename(current_cycle_start)
    current_cycle_end_fmt = format_date_for_filename(current_cycle_end)
    next_cycle_start_fmt = format_date_for_filename(next_cycle_start)
    next_cycle_end_fmt = format_date_for_filename(next_cycle_end)
    
    # Define filenames
    current_cooling_filename = f"2-Week Cooling Period ({current_cooling_start_fmt} - {current_cooling_end_fmt}).md"
    next_cooling_filename = f"2-Week Cooling Period ({next_cooling_start_fmt} - {next_cooling_end_fmt}).md"
    current_cycle_filename = f"6-Week Cycle ({current_cycle_start_fmt} - {current_cycle_end_fmt}).md"
    next_cycle_filename = f"6-Week Cycle ({next_cycle_start_fmt} - {next_cycle_end_fmt}).md"
    
    files_to_create = [
        (current_cooling_filename, "current 2-week cooling period"),
        (next_cooling_filename, "next 2-week cooling period"),
        (current_cycle_filename, "current 6-week cycle"),
        (next_cycle_filename, "next 6-week cycle")
    ]
    
    # Create files if they don't exist
    for filename, description in files_to_create:
        file_path = f"{weekly_cycles_path}/{filename}"
        
        try:
            # Check if file exists
            dbx.files_get_metadata(file_path)
            print(f"File for {description} already exists: {filename}")
        except dropbox.exceptions.ApiError as e:
            if isinstance(e.error, dropbox.files.GetMetadataError):
                print(f"File for {description} does not exist. Creating it now.")
                try:
                    # Create an empty file
                    dbx.files_upload(b"", file_path)
                    print(f"Created file for {description}: {filename}")
                except dropbox.exceptions.ApiError as upload_error:
                    print(f"Error creating file for {description}: {upload_error}")
            else:
                print(f"Dropbox API error for {description}: {e}")

def main():
    print("Cycle Files Creator for Obsidian with Dropbox Integration")
    print("========================================================")
    
    # Display current variables
    print("\nBEFORE ANY UPDATES:")
    display_cycle_variables()
    
    # Resolve cycle dates in Redis if needed
    changes_made = resolve_cycle_dates()
    
    if changes_made:
        print("\nAFTER UPDATES:")
        display_cycle_variables()
    else:
        print("\nNo updates were needed for cycle dates.")
    
    # Get the vault path from environment variable
    dropbox_vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not dropbox_vault_path:
        print("Error: DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set")
        sys.exit(1)
    
    try:
        # Find the Cycles folder
        cycles_folder_path = find_cycles_folder(dropbox_vault_path)
        print(f"Found cycles folder: {cycles_folder_path}")
        
        # Ensure the _6-Week-Cycles folder exists
        six_week_cycles_path = ensure_six_week_cycles_folder(cycles_folder_path)
        print(f"Using 6-week cycles folder: {six_week_cycles_path}")
        
        # Create cycle files
        create_cycle_files(six_week_cycles_path)
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except dropbox.exceptions.AuthError as e:
        print(f"Dropbox authentication error: {e}")
        print("Please make sure your Dropbox access token is valid and has the correct permissions.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)
    
    print("\nAll operations completed successfully.")

if __name__ == "__main__":
    main()
