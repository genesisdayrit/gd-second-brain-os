#!/usr/bin/env python3
"""
Cron Log Cleanup Script

This script clears out log files in the cron_logs directory to prevent 
excessive disk usage over time.

Usage:
    python clear_cron_logs.py [--dry-run] [--keep-days N] [--backup]
    
Options:
    --dry-run       Show what would be deleted without actually deleting
    --keep-days N   Keep logs from the last N days (default: 7)
    --backup        Create a backup of logs before deletion
    --all           Delete all log files regardless of age
"""

import os
import sys
import argparse
import glob
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def get_script_directory():
    """Get the directory where this script is located (cron_logs folder)"""
    return Path(__file__).parent.absolute()


def get_log_files(log_dir):
    """Get all .log files in the directory"""
    log_pattern = os.path.join(log_dir, "*.log")
    return glob.glob(log_pattern)


def is_file_older_than_days(file_path, days):
    """Check if a file is older than the specified number of days"""
    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
    cutoff_date = datetime.now() - timedelta(days=days)
    return file_mtime < cutoff_date


def backup_logs(log_files, backup_dir):
    """Create a backup of log files before deletion"""
    if not log_files:
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"cron_logs_backup_{timestamp}"
    backup_path.mkdir(exist_ok=True)
    
    print(f"Creating backup in: {backup_path}")
    
    for log_file in log_files:
        file_name = os.path.basename(log_file)
        shutil.copy2(log_file, backup_path / file_name)
        print(f"  Backed up: {file_name}")


def clear_logs(log_dir, keep_days=None, dry_run=False, create_backup=False, delete_all=False):
    """
    Clear log files based on the specified criteria
    
    Args:
        log_dir: Directory containing log files
        keep_days: Keep files newer than this many days (None means delete all)
        dry_run: If True, show what would be deleted without actually deleting
        create_backup: If True, create backup before deletion
        delete_all: If True, delete all log files regardless of age
    """
    log_files = get_log_files(log_dir)
    
    if not log_files:
        print("No log files found in the cron_logs directory.")
        return
    
    files_to_delete = []
    
    if delete_all or keep_days is None:
        files_to_delete = log_files
    else:
        for log_file in log_files:
            if is_file_older_than_days(log_file, keep_days):
                files_to_delete.append(log_file)
    
    if not files_to_delete:
        if keep_days:
            print(f"No log files older than {keep_days} days found.")
        else:
            print("No log files to delete.")
        return
    
    print(f"Found {len(files_to_delete)} log file(s) to delete:")
    for log_file in files_to_delete:
        file_size = os.path.getsize(log_file)
        file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
        print(f"  - {os.path.basename(log_file)} ({file_size} bytes, modified: {file_mtime.strftime('%Y-%m-%d %H:%M:%S')})")
    
    if dry_run:
        print("\n[DRY RUN] No files were actually deleted.")
        return
    
    # Create backup if requested
    if create_backup:
        backup_logs(files_to_delete, log_dir)
    
    # Delete the files
    deleted_count = 0
    total_size_freed = 0
    
    for log_file in files_to_delete:
        try:
            file_size = os.path.getsize(log_file)
            os.remove(log_file)
            deleted_count += 1
            total_size_freed += file_size
            print(f"  ✓ Deleted: {os.path.basename(log_file)}")
        except OSError as e:
            print(f"  ✗ Failed to delete {os.path.basename(log_file)}: {e}")
    
    print(f"\nCleanup complete!")
    print(f"Deleted {deleted_count} file(s)")
    print(f"Freed up {total_size_freed:,} bytes ({total_size_freed / 1024:.2f} KB)")


def main():
    parser = argparse.ArgumentParser(
        description="Clear cron log files to free up disk space",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python clear_cron_logs.py                           # Delete all logs (default)
    python clear_cron_logs.py --dry-run                 # See what would be deleted
    python clear_cron_logs.py --keep-days 30            # Keep last 30 days of logs
    python clear_cron_logs.py --backup                  # Delete all logs with backup
    python clear_cron_logs.py --keep-days 7 --backup    # Keep 7 days, backup deleted files
        """
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    
    parser.add_argument(
        "--keep-days", 
        type=int, 
        help="Keep logs from the last N days (by default, all logs are deleted)"
    )
    
    parser.add_argument(
        "--backup", 
        action="store_true",
        help="Create a backup of logs before deletion"
    )
    
    parser.add_argument(
        "--all", 
        action="store_true",
        help="Delete all log files regardless of age"
    )
    
    args = parser.parse_args()
    
    # Get the cron_logs directory (where this script is located)
    log_dir = get_script_directory()
    
    print(f"Cron Log Cleanup Script")
    print(f"Target directory: {log_dir}")
    print("-" * 50)
    
    # Validate arguments
    if args.all and args.keep_days is not None:
        print("Warning: --all flag overrides --keep-days setting")
    
    try:
        clear_logs(
            log_dir=log_dir,
            keep_days=args.keep_days,
            dry_run=args.dry_run,
            create_backup=args.backup,
            delete_all=args.all or args.keep_days is None
        )
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
