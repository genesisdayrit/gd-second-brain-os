import os
import re
import redis
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')  # Default to 'localhost' if not set
redis_port = int(os.getenv('REDIS_PORT', 6379))    # Default to 6379 if not set
redis_password = os.getenv('REDIS_PASSWORD', None)  # Default to None if not set

# Connect to Redis using the environment variables
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)

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

def validate_date_format(date_str):
    """Validate that the date string is in YYYY-MM-DD format."""
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, date_str):
        return False
    
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def get_date_input(prompt_message):
    """Get a date input from the user in YYYY-MM-DD format."""
    while True:
        date_str = input(prompt_message)
        if validate_date_format(date_str):
            return date_str
        else:
            print("Invalid date format. Please use YYYY-MM-DD (e.g., 2025-04-05).")

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

def handle_two_week_cooling_period():
    """Handle the two-week cooling period workflow."""
    existing_start_date = r.get('two_week_cooling_period_start_date')
    
    if existing_start_date:
        print(f"Current two-week cooling period start date: {existing_start_date}")
        override = input("Would you like to override this date? (y/n): ").lower() == 'y'
        if not override:
            return
    else:
        create = input("No two-week cooling period start date found. Would you like to create one? (y/n): ").lower() == 'y'
        if not create:
            return
    
    start_date = get_date_input("Enter the two-week cooling period start date (YYYY-MM-DD): ")
    dates = calculate_two_week_cooling_periods(start_date)
    
    # Store all calculated dates in Redis
    for key, value in dates.items():
        r.set(key, value)
    
    print("\nTwo-week cooling period dates updated in Redis:")
    for key, value in dates.items():
        print(f"  {key}: {value}")

def handle_six_week_cycle():
    """Handle the six-week cycle workflow."""
    existing_start_date = r.get('6_week_cycle_start_date')
    
    if existing_start_date:
        print(f"Current six-week cycle start date: {existing_start_date}")
        override = input("Would you like to override this date? (y/n): ").lower() == 'y'
        if not override:
            return
    else:
        create = input("No six-week cycle start date found. Would you like to create one? (y/n): ").lower() == 'y'
        if not create:
            return
    
    start_date = get_date_input("Enter the six-week cycle start date (YYYY-MM-DD): ")
    dates = calculate_six_week_cycles(start_date)
    
    # Store all calculated dates in Redis
    for key, value in dates.items():
        r.set(key, value)
    
    print("\nSix-week cycle dates updated in Redis:")
    for key, value in dates.items():
        print(f"  {key}: {value}")

def main():
    """Main function to run the interactive workflow."""
    print("Cycle Dates Manager for Redis")
    print("-----------------------------")
    
    try:
        # Test Redis connection
        r.ping()
        print("Connected to Redis successfully.")
    except redis.ConnectionError:
        print("Error: Could not connect to Redis. Please check your connection settings.")
        return
    
    # Display all variables at the beginning
    print("\nBEFORE UPDATES:")
    display_cycle_variables()
    
    # Interactive workflow for updating dates
    handle_two_week_cooling_period()
    print()
    handle_six_week_cycle()
    
    # Display all variables at the end
    print("\nAFTER UPDATES:")
    display_cycle_variables()
    
    print("\nAll operations completed.")

if __name__ == "__main__":
    main()
