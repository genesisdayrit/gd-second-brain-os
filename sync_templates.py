import os
import shutil
from dotenv import load_dotenv

# Load environment variables from .env file, if available
load_dotenv()

def find_or_create_target_template_directory(base_path):
    """Search for or create a directory within the base path that ends with '_Templates'."""
    template_dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and d.endswith('_Templates')]
    
    if len(template_dirs) == 0:
        # If no _Templates directory exists, create one
        target_templates_dir = os.path.join(base_path, "_Templates")
        os.makedirs(target_templates_dir)
        print(f"No '_Templates' directory found. Created: {target_templates_dir}")
        return target_templates_dir
    elif len(template_dirs) > 1:
        raise ValueError(f"Multiple directories ending with '_Templates' found: {template_dirs}. Please ensure only one such directory exists.")
    
    return os.path.join(base_path, template_dirs[0])

def sync_directories_and_files(template_dir, target_templates_dir):
    """Synchronize directories and files from the template to the target path."""
    
    # Traverse the template directory and copy files and folders
    for root, dirs, files in os.walk(template_dir):
        relative_path = os.path.relpath(root, template_dir)
        target_dir = os.path.join(target_templates_dir, relative_path)
        
        # Create directory if it does not exist
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            print(f"Created directory: {target_dir}")

        # Copy or overwrite files
        for file in files:
            src_file = os.path.join(root, file)
            dest_file = os.path.join(target_dir, file)
            if not os.path.exists(dest_file):
                shutil.copy2(src_file, dest_file)
                print(f"Copied file: {src_file} to {dest_file}")
            else:
                shutil.copy2(src_file, dest_file)
                print(f"File already exists and was overwritten: {dest_file}")

def main():
    # Use the environment variable to determine the target base path
    base_path = os.getenv('OBSIDIAN_VAULT_BASE_PATH')
    if not base_path or not os.path.exists(base_path):
        raise EnvironmentError("OBSIDIAN_VAULT_BASE_PATH environment variable is not set or points to an invalid path.")
    
    # Find the 'templates' directory in the same directory as the script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(current_dir, "templates")
    
    if not os.path.exists(template_dir):
        raise FileNotFoundError(f"Template directory does not exist: {template_dir}")
    
    try:
        # Find or create the target directory that ends with '_Templates'
        target_templates_dir = find_or_create_target_template_directory(base_path)
        print(f"Target template directory found or created: {target_templates_dir}")
    except (FileNotFoundError, ValueError) as e:
        print(e)
        return
    
    # Synchronize the directories and files
    sync_directories_and_files(template_dir, target_templates_dir)
    print("Synchronization complete.")

if __name__ == "__main__":
    main()
