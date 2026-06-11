#!/usr/bin/env python3
"""
Cleanup script to remove temporary files older than 1 day.
Run this script periodically using cron or a task scheduler.
"""

import os
import time
import logging
import tempfile
import shutil
import glob

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='cleanup.log'
)

# Define the temporary directory paths to clean
# Add your application's specific paths here
CLEANUP_PATHS = [
    tempfile.gettempdir(),  # Standard temp directory
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_data")  # Create this directory if you use it
]

# Time threshold (24 hours = 86400 seconds)
ONE_DAY_IN_SECONDS = 86400

def cleanup_old_files():
    """Remove files and directories older than 1 day."""
    current_time = time.time()
    deleted_count = 0
    
    for cleanup_path in CLEANUP_PATHS:
        if not os.path.exists(cleanup_path):
            logging.info(f"Directory {cleanup_path} doesn't exist, skipping")
            continue
            
        logging.info(f"Scanning directory: {cleanup_path}")
        
        # Check for .zip files from shapefile downloads
        zip_pattern = os.path.join(cleanup_path, "*.zip")
        for file_path in glob.glob(zip_pattern):
            try:
                # Get file's last modification time
                file_age = current_time - os.path.getmtime(file_path)
                
                if file_age > ONE_DAY_IN_SECONDS:
                    os.remove(file_path)
                    logging.info(f"Deleted old file: {file_path}")
                    deleted_count += 1
            except Exception as e:
                logging.error(f"Error while trying to delete {file_path}: {str(e)}")
        
        # Check for temporary directories created by our app
        for item in os.listdir(cleanup_path):
            full_path = os.path.join(cleanup_path, item)
            
            # Skip if it's not a directory or doesn't match our temp dir pattern
            if not os.path.isdir(full_path):
                continue
                
            # Only process directories that match temporary directory patterns
            # This avoids deleting important directories
            if item.startswith('tmp') or item.startswith('temp_'):
                try:
                    # Get directory's last modification time
                    dir_age = current_time - os.path.getmtime(full_path)
                    
                    if dir_age > ONE_DAY_IN_SECONDS:
                        shutil.rmtree(full_path)
                        logging.info(f"Deleted old directory: {full_path}")
                        deleted_count += 1
                except Exception as e:
                    logging.error(f"Error while trying to delete {full_path}: {str(e)}")
    
    logging.info(f"Cleanup complete. Deleted {deleted_count} items.")
    return deleted_count

if __name__ == "__main__":
    try:
        logging.info("Starting cleanup process")
        deleted = cleanup_old_files()
        logging.info(f"Cleanup finished. Removed {deleted} old files/directories.")
    except Exception as e:
        logging.error(f"Error during cleanup: {str(e)}")
