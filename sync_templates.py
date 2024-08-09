import os
import shutil

def get_user_input_path():
    """Prompt user to input the target path."""
    user_input_path = input("Please enter the path where you want to synchronize the templates: ")
    if not os.path.exists(user_input_path):
        print(f"The path {user_input_path} does not exist. Please enter a valid path.")
        return get_user_input_path()
    return user_input_path

def sync_directories_and_files(template_dir, user_input_path):
    """Synchronize directories and files from the template to the user input path."""
    # Define the _Templates directory in the target path
    target_templates_dir = os.path.join(user_input_path, "_Templates")
    
    # Create the _Templates directory if it doesn't exist
    if not os.path.exists(target_templates_dir):
        os.makedirs(target_templates_dir)
        print(f"Created directory: {target_templates_dir}")

    # Traverse the template directory and copy files and folders
    for root, dirs, files in os.walk(template_dir):
        relative_path = os.path.relpath(root, template_dir)
        target_dir = os.path.join(target_templates_dir, relative_path)
        
        # Create directory if it does not exist
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            print(f"Created directory: {target_dir}")

        # Copy files if they do not exist
        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(target_dir, file)
            if not os.path.exists(dest_file):
                shutil.copy2(src_file, dest_file)
                print(f"Copied file: {src_file} to {dest_file}")
            else:
                print(f"File already exists: {dest_file}")

def main():
    # Assume the script is run from the root of the project where the templates directory exists
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(current_dir, "templates")
    
    if not os.path.exists(template_dir):
        print(f"Template directory does not exist: {template_dir}")
        return
    
    user_input_path = get_user_input_path()
    sync_directories_and_files(template_dir, user_input_path)
    print("Synchronization complete.")

if __name__ == "__main__":
    main()
