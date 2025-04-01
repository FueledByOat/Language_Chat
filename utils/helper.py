"""
helper.py

This module provides functions to help with the tidy operations of the main program.  
"""

import os

# Constants
LOCAL_AUDIO_FILES = "audio"

# Variables

def cleanup(dir = LOCAL_AUDIO_FILES):
    try:
        # List all files in the directory
        files = os.listdir(dir)

        for file_name in files:
            # Construct full file path
            file_path = os.path.join(dir, file_name)

            # Check if it is a file (and not a directory)
            if os.path.isfile(file_path):
                # Delete the file
                os.remove(file_path)
                print(f"Deleted: {file_path}")

        print("All files deleted successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
    