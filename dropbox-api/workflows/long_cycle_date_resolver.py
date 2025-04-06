import os
import redis
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Redis configuration from environment variables
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)

# Connect to Redis
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

def main():
    print("Cycle Overlap Resolver")
    print("---------------------")
    
    # Display all variables at the beginning
    print("\nBEFORE UPDATES:")
    display_cycle_variables()
    
    # Get today's date using system time
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\nUsing current date: {today}")
    today_date = datetime.strptime(today, '%Y-%m-%d')
    
    # Get current values from Redis
    cooling_start = r.get('two_week_cooling_period_start_date')
    cooling_end = r.get('two_week_cooling_period_end_date')
    cycle_start = r.get('6_week_cycle_start_date')
    cycle_end = r.get('6_week_cycle_end_date')
    
    # Check if values exist in Redis
    if not cooling_start or not cooling_end or not cycle_start or not cycle_end:
        print("Error: One or more required dates not found in Redis.")
        print("Please run the dropbox-api/workflows/update_long_cycle_start_dates.py script to set up cycle dates.")
        return
    
    # Convert string dates to datetime objects
    cooling_start_date = datetime.strptime(cooling_start, '%Y-%m-%d')
    cooling_end_date = datetime.strptime(cooling_end, '%Y-%m-%d')
    cycle_start_date = datetime.strptime(cycle_start, '%Y-%m-%d')
    cycle_end_date = datetime.strptime(cycle_end, '%Y-%m-%d')
    
    # Print current date information for debugging
    print(f"Current 2-week cooling period: {cooling_start} to {cooling_end}")
    print(f"Current 6-week cycle: {cycle_start} to {cycle_end}")
    
    # Check which period we're in
    in_cooling_period = is_date_between(today_date, cooling_start_date, cooling_end_date)
    in_six_week_cycle = is_date_between(today_date, cycle_start_date, cycle_end_date)
    
    # Debug which period we're in
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
        elif cooling_start_date > today_date and cycle_start_date > today_date:
            # Both periods are in the future
            print("Both periods are scheduled to start in the future.")
            if cooling_start_date < cycle_start_date:
                print(f"The 2-week cooling period will start next on {cooling_start}")
            else:
                print(f"The 6-week cycle will start next on {cycle_start}")
            print("No adjustments needed.")
        else:
            print("Cycles may need manual adjustment:")
            print(f"2-week cooling period: {cooling_start} to {cooling_end}")
            print(f"6-week cycle: {cycle_start} to {cycle_end}")
            print("To manually adjust cycle dates, please run dropbox-api/workflows/update_long_cycle_start_dates.py")
    
    # Display all variables at the end
    print("\nAFTER UPDATES:")
    display_cycle_variables()

if __name__ == "__main__":
    main()
