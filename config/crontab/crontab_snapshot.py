import subprocess
import datetime

# Get current datetime
now = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")

# Define filename with timestamp
filename = f"crontab_{now}.txt"

# Run `crontab -l` to get the current crontab
try:
    crontab_output = subprocess.check_output(["crontab", "-l"], stderr=subprocess.DEVNULL, text=True)
    
    # Write to file
    with open(filename, "w") as file:
        file.write(crontab_output)

    print(f"Crontab snapshot saved to {filename}")

except subprocess.CalledProcessError:
    print("No crontab found or an error occurred.")
