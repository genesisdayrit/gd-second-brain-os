import os

# List of folders to create
folders = [
    "_Affirm",
    "_Cycles",
    "_Daily Action",
    "_Experiences+Events+Meetings+Sessions",
    "_Journal",
    "_Knowledge-Hub",
    "_Master-Vision",
    "_Months",
    "_Newsletters",
    "_Notes+Ideas",
    "_People",
    "_Places",
    "_Products+Consumption+Things",
    "_Quarters",
    "_Templates",
    "_Weeks",
    "_Writing",
    "_Years"
]

# Function to create folders
def create_folders(base_path):
    try:
        for folder in folders:
            folder_path = os.path.join(base_path, folder)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                print(f"Created folder: {folder_path}")
            else:
                print(f"Folder already exists: {folder_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Main execution
if __name__ == "__main__":
    user_path = input("Enter the path where you want to create the folders: ")
    if os.path.exists(user_path):
        create_folders(user_path)
    else:
        print("The path you entered does not exist.")
