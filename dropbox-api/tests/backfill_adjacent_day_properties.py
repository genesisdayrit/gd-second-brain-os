import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

import yaml
import redis
import dropbox
from dotenv import load_dotenv

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Load Environment Variables ---
load_dotenv()

PROJECT_ROOT_PATH = os.getenv('PROJECT_ROOT_PATH')
if PROJECT_ROOT_PATH:
    load_dotenv(dotenv_path=Path(PROJECT_ROOT_PATH) / '.env')

# --- Redis Configuration ---
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)


def get_dropbox_access_token():
    """Retrieve the Dropbox access token from Redis."""
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token


# --- Date / Filename Helpers ---
# Journal files are named like "Jun 6, 2026.md" (no leading zero on the day).
def format_journal_date(date_obj):
    """Format a date as the journal filename stem, e.g. 'Jun 6, 2026'."""
    return f"{date_obj.strftime('%b')} {date_obj.day}, {date_obj.strftime('%Y')}"


def parse_journal_date(file_name):
    """
    Parse a journal filename like 'Jun 6, 2026.md' into a date object.
    Returns None if the name does not match the expected journal pattern.
    """
    stem = file_name[:-3] if file_name.lower().endswith('.md') else file_name
    try:
        # '%d' tolerates both zero-padded and non-padded days on Linux/macOS.
        return datetime.strptime(stem, '%b %d, %Y')
    except ValueError:
        return None


# --- Dropbox Folder Lookup ---
def find_subfolder(folder_path, suffix):
    """Find a subfolder of folder_path whose name ends with the given suffix."""
    response = dbx.files_list_folder(folder_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith(suffix):
            return entry.path_lower
    raise FileNotFoundError(f"Could not find a folder ending with '{suffix}' in '{folder_path}'")


def list_all_files_in_folder(folder_path):
    """List every file entry in a folder, handling pagination."""
    all_files = []
    response = dbx.files_list_folder(folder_path)
    while True:
        all_files.extend(response.entries)
        if not response.has_more:
            break
        response = dbx.files_list_folder_continue(response.cursor)
    return all_files


# --- YAML Helpers (mirrors update_daily_properties.py) ---
def extract_yaml_metadata(file_content):
    """
    Extract YAML front matter from the file content.
    Returns a tuple (metadata, remaining_content). On parse failure returns (None, None).
    If there is no front matter, returns ({}, original_content).
    """
    lines = file_content.splitlines()
    if lines and lines[0].strip() == "---":
        yaml_lines = []
        content_start = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                content_start = i + 1
                break
            yaml_lines.append(line)
        yaml_str = "\n".join(yaml_lines)
        try:
            metadata = yaml.safe_load(yaml_str) or {}
            remaining_content = "\n".join(lines[content_start:]) if content_start is not None else ""
            return metadata, remaining_content
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML: {e}")
            return None, None
    return {}, file_content


def build_file_content(metadata, content):
    """Serialize metadata back into YAML front matter and reattach the body."""
    yaml_str = yaml.safe_dump(metadata, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n{content}"


def set_adjacent_day_properties(metadata, expected_prev, expected_next):
    """
    Set 'Previous Day' and 'Next Day' while matching the layout the daily
    properties generator produces: the two keys sit immediately after
    'On this Day'. If 'On this Day' is absent, fall back to appending them
    (preserving where they already are if present). Returns a new ordered dict.
    """
    rebuilt = {}
    placed = False
    for key, value in metadata.items():
        if key in ("Previous Day", "Next Day"):
            # Drop existing instances; we re-emit them in canonical position.
            continue
        rebuilt[key] = value
        if key == "On this Day":
            rebuilt["Previous Day"] = expected_prev
            rebuilt["Next Day"] = expected_next
            placed = True

    if not placed:
        rebuilt["Previous Day"] = expected_prev
        rebuilt["Next Day"] = expected_next

    return rebuilt


# --- Core Backfill Logic ---
def backfill_journal(file_path, file_name, journal_date, only_missing=False, dry_run=False):
    """
    Add/update the 'Previous Day' and 'Next Day' properties on a single journal,
    calculated relative to the journal's own date.
    Returns one of: 'updated', 'skipped', 'error'.
    """
    expected_prev = [f"[[{format_journal_date(journal_date - timedelta(days=1))}]]"]
    expected_next = [f"[[{format_journal_date(journal_date + timedelta(days=1))}]]"]

    try:
        _, response = dbx.files_download(file_path)
        file_content = response.content.decode('utf-8')
    except dropbox.exceptions.ApiError as e:
        logger.error(f"  Error downloading {file_name}: {e}")
        return 'error'

    # A properly formatted journal note always opens with YAML front matter.
    # Anything else is likely a misplaced note, so skip it untouched.
    lines = file_content.splitlines()
    if not (lines and lines[0].strip() == "---"):
        logger.info(f"  {file_name}: no YAML front matter (not a journal note). Skipping.")
        return 'skipped'

    metadata, remaining_content = extract_yaml_metadata(file_content)
    if metadata is None:
        logger.warning(f"  {file_name}: malformed YAML front matter. Skipping.")
        return 'skipped'

    if only_missing and metadata.get("Previous Day") is not None and metadata.get("Next Day") is not None:
        logger.info(f"  {file_name}: already has both properties (only-missing mode). Skipping.")
        return 'skipped'

    if metadata.get("Previous Day") == expected_prev and metadata.get("Next Day") == expected_next:
        logger.info(f"  {file_name}: already correct. Skipping.")
        return 'skipped'

    metadata = set_adjacent_day_properties(metadata, expected_prev, expected_next)

    logger.info(f"  {file_name}: Previous Day -> {expected_prev[0]}, Next Day -> {expected_next[0]}")

    if dry_run:
        return 'updated'

    new_file_content = build_file_content(metadata, remaining_content)
    # Upload to the ORIGINAL-cased filename. Dropbox is case-preserving, so
    # overwriting at the lowercased path_lower would rename the file to lowercase.
    parent_dir = file_path.rsplit('/', 1)[0]
    upload_path = f"{parent_dir}/{file_name}"
    try:
        dbx.files_upload(
            new_file_content.encode('utf-8'),
            upload_path,
            mode=dropbox.files.WriteMode.overwrite
        )
    except dropbox.exceptions.ApiError as e:
        logger.error(f"  Error uploading {file_name}: {e}")
        return 'error'
    return 'updated'


def main():
    parser = argparse.ArgumentParser(
        description="Backfill 'Previous Day' / 'Next Day' properties on all journal entries."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing to Dropbox.")
    parser.add_argument("--only-missing", action="store_true",
                        help="Only touch journals missing one of the properties (don't correct existing values).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N journals (useful for testing).")
    args = parser.parse_args()

    vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not vault_path:
        logger.error("DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set.")
        sys.exit(1)

    global dbx
    dbx = dropbox.Dropbox(get_dropbox_access_token())

    try:
        daily_folder = find_subfolder(vault_path, "_Daily")
        journal_folder = find_subfolder(daily_folder, "_Journal")
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

    logger.info(f"Journal folder: {journal_folder}")
    if args.dry_run:
        logger.info("DRY RUN: no files will be modified.")

    entries = list_all_files_in_folder(journal_folder)
    journals = []
    for entry in entries:
        if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith('.md'):
            journal_date = parse_journal_date(entry.name)
            if journal_date is None:
                logger.warning(f"Skipping unrecognized filename: {entry.name}")
                continue
            journals.append((entry.path_lower, entry.name, journal_date))

    # Process chronologically for readable logs.
    journals.sort(key=lambda j: j[2])
    if args.limit is not None:
        journals = journals[:args.limit]

    logger.info(f"Found {len(journals)} journal file(s) to process.")

    counts = {'updated': 0, 'skipped': 0, 'error': 0}
    for file_path, file_name, journal_date in journals:
        result = backfill_journal(
            file_path, file_name, journal_date,
            only_missing=args.only_missing, dry_run=args.dry_run
        )
        counts[result] += 1

    verb = "Would update" if args.dry_run else "Updated"
    logger.info(
        f"Done. {verb}: {counts['updated']}, Skipped: {counts['skipped']}, Errors: {counts['error']}"
    )
    if counts['error'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
