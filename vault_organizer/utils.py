"""
Utility functions for file operations and logging.
"""

import os
import shutil
import fnmatch
from datetime import datetime
from pathlib import Path


def get_logger_path():
    """Get the path for the organizer log file."""
    log_dir = Path.home() / ".gd-second-brain-os"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "organizer.log"


def log_move(source: str, destination: str, success: bool = True, error: str = None):
    """Log a file move operation."""
    log_path = get_logger_path()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "SUCCESS" if success else "FAILED"
    entry = f"[{timestamp}] {status}: {source} -> {destination}"
    if error:
        entry += f" (Error: {error})"
    entry += "\n"
    
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)


def find_root_markdown_files(vault_path: str, pattern: str = None) -> list:
    """
    Find all markdown files in the vault root.
    
    Args:
        vault_path: Path to the Obsidian vault
        pattern: Optional glob pattern to filter files
    
    Returns:
        List of full paths to markdown files in the root
    """
    if not os.path.exists(vault_path):
        raise FileNotFoundError(f"Vault path not found: {vault_path}")
    
    files = []
    for item in os.listdir(vault_path):
        # Skip hidden files, directories, and non-markdown files
        if item.startswith('.'):
            continue
        if not item.endswith('.md'):
            continue
        
        full_path = os.path.join(vault_path, item)
        if not os.path.isfile(full_path):
            continue
        
        # Apply pattern filter if specified
        if pattern and not fnmatch.fnmatch(item, pattern):
            continue
        
        files.append(full_path)
    
    # Sort for consistent ordering
    files.sort()
    return files


def ensure_folder_exists(vault_path: str, folder_path: str):
    """
    Ensure a folder (and any subfolders) exist in the vault.
    
    Args:
        vault_path: Base path of the vault
        folder_path: Relative path to the folder (e.g., "14_CRM/_People")
    """
    full_path = os.path.join(vault_path, folder_path)
    os.makedirs(full_path, exist_ok=True)
    return full_path


def move_file_to_folder(source_path: str, vault_path: str, folder_path: str) -> str:
    """
    Move a file to a destination folder within the vault.
    
    Args:
        source_path: Full path to the source file
        vault_path: Base path of the vault
        folder_path: Relative path to the destination folder
    
    Returns:
        Full path to the destination file
    """
    filename = os.path.basename(source_path)
    dest_folder = ensure_folder_exists(vault_path, folder_path)
    dest_path = os.path.join(dest_folder, filename)
    
    # Handle filename collision
    if os.path.exists(dest_path):
        base, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{base}_{timestamp}{ext}"
        dest_path = os.path.join(dest_folder, new_filename)
        print(f"  Note: Filename collision detected, renamed to: {new_filename}")
    
    # Perform the move
    shutil.move(source_path, dest_path)
    return dest_path


def get_display_path(full_path: str, vault_path: str) -> str:
    """Get a relative display path from vault root."""
    return full_path.replace(vault_path, "").lstrip("/")
