import os
import sys
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path

import redis
import dropbox
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
PROJECT_ROOT_PATH = os.getenv('PROJECT_ROOT_PATH')
if PROJECT_ROOT_PATH:
    load_dotenv(dotenv_path=Path(PROJECT_ROOT_PATH) / '.env')

redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_password = os.getenv('REDIS_PASSWORD', None)
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True)


def get_dropbox_access_token():
    access_token = r.get('DROPBOX_ACCESS_TOKEN')
    if not access_token:
        raise EnvironmentError("Error: Dropbox access token not found in Redis.")
    return access_token


def canonical_journal_name(date_obj):
    """Canonical journal filename, e.g. 'Apr 19, 2026.md'."""
    return f"{date_obj.strftime('%b')} {date_obj.day}, {date_obj.strftime('%Y')}.md"


def parse_journal_date(file_name):
    """Parse 'Apr 19, 2026.md' (case-insensitive) into a date; None if not a journal name."""
    stem = file_name[:-3] if file_name.lower().endswith('.md') else file_name
    try:
        return datetime.strptime(stem, '%b %d, %Y')
    except ValueError:
        return None


def find_subfolder(folder_path, suffix):
    response = dbx.files_list_folder(folder_path)
    for entry in response.entries:
        if isinstance(entry, dropbox.files.FolderMetadata) and entry.name.endswith(suffix):
            return entry.path_lower
    raise FileNotFoundError(f"Could not find a folder ending with '{suffix}' in '{folder_path}'")


def list_all_files_in_folder(folder_path):
    all_files = []
    response = dbx.files_list_folder(folder_path)
    while True:
        all_files.extend(response.entries)
        if not response.has_more:
            break
        response = dbx.files_list_folder_continue(response.cursor)
    return all_files


def move_with_retry(from_path, to_path, attempts=6):
    """
    Move a file, retrying on transient 'conflict' errors. Dropbox can briefly
    report a conflict when the destination path differs only by case from a
    just-vacated source path, so we back off and retry.
    """
    for attempt in range(attempts):
        try:
            dbx.files_move_v2(from_path, to_path, autorename=False)
            return
        except dropbox.exceptions.ApiError as e:
            is_conflict = (
                isinstance(e.error, dropbox.files.RelocationError)
                and e.error.is_to()
                and e.error.get_to().is_conflict()
            )
            if is_conflict and attempt < attempts - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


TMP_PREFIX = "__casefix__"


def recover_temp_files(entries, folder, dry_run):
    """Finish any rename that was interrupted, leaving a '__casefix__' temp file."""
    temps = [e for e in entries
             if isinstance(e, dropbox.files.FileMetadata) and e.name.startswith(TMP_PREFIX)]
    if not temps:
        return 0, 0
    logger.info(f"Recovering {len(temps)} leftover temp file(s) from a prior interrupted run...")
    recovered = errors = 0
    for entry in temps:
        final_name = entry.name[len(TMP_PREFIX):]
        to_path = f"{folder}/{final_name}"
        logger.info(f"  recover {entry.name}  ->  {final_name}")
        if dry_run:
            recovered += 1
            continue
        try:
            move_with_retry(entry.path_display, to_path)
            recovered += 1
        except dropbox.exceptions.ApiError as e:
            logger.error(f"    Error recovering {entry.name}: {e}")
            errors += 1
    return recovered, errors


def main():
    parser = argparse.ArgumentParser(
        description="Restore proper casing on journal filenames (e.g. 'apr 19, 2026.md' -> 'Apr 19, 2026.md')."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Actually rename files. Without this flag, only previews changes.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Rename at most N files (useful for a safe test batch).")
    args = parser.parse_args()
    dry_run = not args.apply

    vault_path = os.getenv('DROPBOX_OBSIDIAN_VAULT_PATH')
    if not vault_path:
        logger.error("DROPBOX_OBSIDIAN_VAULT_PATH environment variable not set.")
        sys.exit(1)

    global dbx
    dbx = dropbox.Dropbox(get_dropbox_access_token())

    daily_folder = find_subfolder(vault_path, "_Daily")
    journal_folder = find_subfolder(daily_folder, "_Journal")
    logger.info(f"Journal folder: {journal_folder}")
    if dry_run:
        logger.info("DRY RUN: no files will be renamed. Pass --apply to perform renames.")

    entries = list_all_files_in_folder(journal_folder)
    files_before = sum(1 for e in entries if isinstance(e, dropbox.files.FileMetadata))
    logger.info(f"Total files in folder (baseline): {files_before}")

    # Step 0: heal any interrupted renames before doing anything else.
    recovered, recover_errors = recover_temp_files(entries, journal_folder, dry_run)

    renamed = errors = 0
    for entry in entries:
        if args.limit is not None and renamed >= args.limit:
            break
        if not (isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith('.md')):
            continue
        if entry.name.startswith(TMP_PREFIX):
            continue  # handled in recovery step
        journal_date = parse_journal_date(entry.name)
        if journal_date is None:
            continue  # not a journal-date file; leave untouched

        correct_name = canonical_journal_name(journal_date)
        if entry.name == correct_name:
            continue  # already correct casing

        from_path = entry.path_display  # path_display preserves the real stored casing
        folder = from_path.rsplit('/', 1)[0]
        tmp_path = f"{folder}/{TMP_PREFIX}{correct_name}"
        to_path = f"{folder}/{correct_name}"
        logger.info(f"  {entry.name}  ->  {correct_name}")

        if dry_run:
            renamed += 1
            continue

        try:
            # Two-step rename: a direct case-only rename is rejected by Dropbox as
            # a conflict, so route through a uniquely-named temp file. autorename=False
            # guarantees we never overwrite a different existing file.
            move_with_retry(from_path, tmp_path)
            move_with_retry(tmp_path, to_path)
            renamed += 1
        except dropbox.exceptions.ApiError as e:
            logger.error(f"    Error renaming {entry.name}: {e}")
            errors += 1

    verb = "Would rename" if dry_run else "Renamed"
    logger.info(f"Done. {verb}: {renamed}, Recovered: {recovered}, Errors: {errors + recover_errors}")

    # Safety check: confirm no files vanished.
    if not dry_run:
        after_entries = list_all_files_in_folder(journal_folder)
        files_after = sum(1 for e in after_entries if isinstance(e, dropbox.files.FileMetadata))
        leftover_temps = sum(1 for e in after_entries
                             if isinstance(e, dropbox.files.FileMetadata) and e.name.startswith(TMP_PREFIX))
        logger.info(f"File count: before={files_before}, after={files_after}, leftover temps={leftover_temps}")
        if files_after != files_before:
            logger.error("FILE COUNT CHANGED! Investigate before running again.")
            sys.exit(1)

    if errors + recover_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
