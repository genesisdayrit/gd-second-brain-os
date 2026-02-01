#!/usr/bin/env python3
"""
Vault Organizer CLI Tool

Manual Obsidian vault file organizer.
Shows common folder destinations - you pick where each file goes.

Usage:
    python organize.py [--limit N] [--pattern GLOB]

Examples:
    python organize.py                    # Process all files
    python organize.py --limit 5          # Process first 5 files
    python organize.py --pattern "*Meeting*"  # Process files matching pattern
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Load environment variables
load_dotenv(os.path.join(root_dir, '.env'))

from vault_organizer.categorizer import get_folder_choices, read_file_title
from vault_organizer.utils import find_root_markdown_files, move_file_to_folder, log_move, get_display_path


def print_header():
    """Print the CLI header."""
    print("\n" + "=" * 60)
    print("  Obsidian Vault Organizer")
    print("  Manual File Organizer")
    print("=" * 60 + "\n")


def print_choices(filename: str, title: str, choices: list):
    """Print the folder choices for manual selection."""
    print(f"\n📄 {filename}")
    if title != filename.replace('.md', ''):
        print(f"   {title}")
    
    for i, (folder, _) in enumerate(choices, 1):
        print(f"  {i}) {folder}")
    
    print()


def get_user_choice(num_options: int) -> str:
    """Get user input for file disposition."""
    valid_choices = [str(i) for i in range(1, num_options + 1)] + ['s', 'q']
    
    while True:
        choice = input(f"Choose [1-{num_options}] to move, [s] to skip, [q] to quit: ").strip().lower()
        
        if choice in valid_choices:
            return choice
        
        print(f"Invalid choice. Please enter 1-{num_options}, s, or q.")





def process_file(file_path: str, vault_path: str, choices: list) -> bool:
    """
    Process a single file with user interaction.
    
    Returns True if user wants to continue, False to quit.
    """
    filename = os.path.basename(file_path)
    title = read_file_title(file_path)
    print_choices(filename, title, choices)
    
    choice = get_user_choice(len(choices))
    
    if choice == 'q':
        return False
    
    if choice == 's':
        print(f"  ⏭️  Skipped: {filename}")
        return True
    
    # User chose a destination
    index = int(choice) - 1
    dest_folder, _ = choices[index]
    
    try:
        dest_path = move_file_to_folder(file_path, vault_path, dest_folder)
        display_dest = get_display_path(dest_path, vault_path)
        print(f"  ✅ Moved to: {display_dest}")
        log_move(file_path, dest_path, success=True)
    except Exception as e:
        print(f"  ❌ Error moving file: {e}")
        log_move(file_path, dest_folder, success=False, error=str(e))
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Manual Obsidian vault file organizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python organize.py                    # Process all root files
  python organize.py --limit 5          # Process first 5 files
  python organize.py --pattern "*Meeting*"  # Process matching files
        """
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='Limit the number of files to process'
    )
    parser.add_argument(
        '--pattern', '-p',
        type=str,
        default=None,
        help='Filter files by glob pattern (e.g., "*Meeting*")'
    )
    
    args = parser.parse_args()
    
    # Get vault path from environment
    vault_path = os.getenv('OBSIDIAN_VAULT_BASE_PATH')
    if not vault_path:
        print("Error: OBSIDIAN_VAULT_BASE_PATH environment variable not set")
        print("Please set it in your .env file")
        sys.exit(1)
    
    print_header()
    print(f"Vault path: {vault_path}\n")
    
    # Find markdown files in root
    try:
        files = find_root_markdown_files(vault_path, pattern=args.pattern)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    if not files:
        print("No markdown files found in vault root.")
        print("Your vault is already organized! 🎉")
        sys.exit(0)
    
    print(f"Found {len(files)} markdown file(s) to process\n")
    
    # Apply limit if specified
    if args.limit:
        files = files[:args.limit]
        print(f"Processing first {len(files)} file(s)\n")
    
    # Get folder choices (static list)
    choices = get_folder_choices()
    
    # Process each file
    processed = 0
    skipped = 0
    
    for file_path in files:
        filename = os.path.basename(file_path)
        
        # Process with user interaction
        should_continue = process_file(file_path, vault_path, choices)
        
        if not should_continue:
            print("\n👋 Quitting. Goodbye!")
            break
        
        processed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"  Done! Processed {processed} file(s)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
