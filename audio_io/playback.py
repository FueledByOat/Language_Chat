"""
audio_io.py

This module provides a function to listen for user input in the Target Language (TL) as well as a function to output the language model translated text in the TL using a voice installed on the host OS.  
"""

import pyaudio
import wave
import pyttsx3

# Constants
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 3
