"""
helper.py

This module provides functions to help with the tidy operations of the main program.  
"""

import os

# Constants
LOCAL_AUDIO_FILE = "human_input.wav"

# Variables

def cleanup(file = LOCAL_AUDIO_FILE):
    """
    Removes the audio file created by the record function
    """
    if os.path.isfile(file):
        os.remove(file)
    