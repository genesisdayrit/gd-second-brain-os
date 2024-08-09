import os

# Custom order of folders (without prefixes)
custom_order = [
    "_Daily",
    "_Weekly",
    "_Writing",
    "_Cycles",
    "_Knowledge-Hub",
    "_Notes+Ideas",
    "_Experiences+Events+Meetings+Sessions",
    "_Monthly",
    "_Quarterly",
    "_Yearly",
    "_Values",
    "_Products+Consumption+Things",
    "_Places",
    "_CRM",
    "_Templates",
]

# Function to find and rename folders based on custom order
def rename_folders(base_path, order):
    try:
        # Gather all folders in the directory
        folders = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))]
        
        # Map to hold the existing folder paths without prefixes
        folder_map = {}
        
        # Populate the folder map
        for folder in folders:
            for name in order:
                if folder.endswith(name):
                    folder_map[name] = folder
                    break
        
        # Rename folders based on the custom order
        for index, name in enumerate(order, start=1):
            if name in folder_map:
                original_path = os.path.join(base_path, folder_map[name])
                new_name = f"{index:02d}{name}"  # Create new name with prefix
                new_path = os.path.join(base_path, new_name)
                
                if original_path != new_path:  # Only rename if the name differs
                    os.rename(original_path, new_path)
                    print(f"Renamed {original_path} to {new_path}")
                else:
                    print(f"No renaming needed for {original_path}")
            else:
                print(f"Folder with suffix {name} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

# Main execution
if __name__ == "__main__":
    user_path = input("Enter the path where the folders are located: ")
    if os.path.exists(user_path):
        rename_folders(user_path, custom_order)
    else:
        print("The path you entered does not exist.")
