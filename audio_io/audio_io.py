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

# Variables

def listen():
    """
    Uses the onboard microphone to record the user speaking in their TL.  Currently, recording continues until a keyboard interrupt is issued with CTRL+C
    """
    with wave.open('human_input.wav', 'wb') as wf:
        p = pyaudio.PyAudio()
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)

        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True)

        # print('Recording...')
        # for _ in range(0, RATE // CHUNK * RECORD_SECONDS):
        #     wf.writeframes(stream.read(CHUNK))
        # print('Done')

        print('\nRecording...Press CTRL+C to end Recording')
        try:
            while True:
                wf.writeframes(stream.read(CHUNK))
        except KeyboardInterrupt:
            pass
        
        print('Done')

        stream.close()
        p.terminate()


def speak(text):
    """
    Uses the onboard speakers and built in language packages to say the text that is passed into the function
    
    Parameters:
    text (string): The text to be spoken by the machine
    """

    
    # Initialize the TTS engine
    engine = pyttsx3.init()

    # Set properties before adding anything to speak
    engine.setProperty('rate', 125)  # Speed percent (can go over 100)
    engine.setProperty('volume', 1)  # Volume 0-1

    # List available voices and set the voice to a Chinese one if available
    voices = engine.getProperty('voices')
    for voice in voices:
        # print(f"Voice: {voice.name}, ID: {voice.id}, Languages: {voice.languages}")
        if 'ZH' in voice.languages or 'ZH-CN' in voice.id:
            engine.setProperty('voice', voice.id)
            break

    # Text to be spoken
    text_to_speak = text

    # Speak the text
    engine.say(text_to_speak)
    engine.runAndWait()