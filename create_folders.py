import os

# Combined folder structure with subfolders and standalone folders
folders_structure = {
    "_Daily": ["_Journal", "_Daily-Action"],
    "_Weeks": ["_Weekly-Maps", "_Weekly-Touches",  "_Newsletters"],
    "_Cycles": ["_Weekly-Cycles", "_6-Week-Cycles"],
    "_Months": ["_Monthy-Review", "_Monthly-External"],
    "_Quarters": ["_Quarterly-Preview", "_Bets", "_Quarterly-Review"],
    "_Years": ["_Annual-Letters", "_Resolutions", "_Mood-Boards"],
    "_Values": ["_Core-Values", "_Principles+Mantras", "_Affirm", "_Master-Vision"],
    "_Experiences+Events+Meetings+Sessions": [],
    "_Knowledge-Hub": [],
    "_Newsletters": [],
    "_Notes+Ideas": [],
    "_CRM": ["_People", "_Companies+Groups+Teams", "_Deals"],
    "_Places": [],
    "_Products+Consumption+Things": [],
    "_Templates": [],
    "_Writing": ["_Drafts", "_Essays"]
}

# Function to create folders with subfolders
def create_folders(base_path, structure):
    try:
        for folder, subfolders in structure.items():
            folder_path = os.path.join(base_path, folder)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                print(f"Created folder: {folder_path}")
            else:
                print(f"Folder already exists: {folder_path}")

            # Create subfolders if they exist
            for subfolder in subfolders:
                subfolder_path = os.path.join(folder_path, subfolder)
                if not os.path.exists(subfolder_path):
                    os.makedirs(subfolder_path)
                    print(f"  Created subfolder: {subfolder_path}")
                else:
                    print(f"  Subfolder already exists: {subfolder_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Main execution
if __name__ == "__main__":
    user_path = input("Enter the path where you want to create the folders: ")
    if os.path.exists(user_path):
        create_folders(user_path, folders_structure)
    else:
        print("The path you entered does not exist.")
