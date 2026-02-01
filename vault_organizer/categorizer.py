"""
Simple file categorization - returns common folder choices for manual selection.
"""

import os
from typing import List, Tuple

from vault_organizer.folder_structure import get_common_folders


def read_file_title(file_path: str) -> str:
    """
    Read file and extract title from first H1 or filename.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return os.path.basename(file_path).replace('.md', '')
    
    # Try to extract title from first H1
    title = os.path.basename(file_path).replace('.md', '')
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('# '):
            title = line[2:].strip()
            break
    
    return title


def get_folder_choices() -> List[Tuple[str, str]]:
    """
    Return the list of common folder choices for manual selection.
    
    Returns list of tuples: (folder_path, description)
    """
    return get_common_folders()
