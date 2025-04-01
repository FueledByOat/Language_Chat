"""
audio_io.py

This module provides a function to listen for user input in the Target Language (TL) as well as a function to output the language model translated text in the TL using a voice installed on the host OS.  
"""

import pyttsx3

def speak(audio_path, text, language = "chinese"):
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
    if language == "chinese":
        for voice in voices:
            # print(f"Voice: {voice.name}, ID: {voice.id}, Languages: {voice.languages}")
            if 'ZH' in voice.languages or 'ZH-CN' in voice.id:
                engine.setProperty('voice', voice.id)
                break
    if language == "japanese":
        for voice in voices:
            # print(f"Voice: {voice.name}, ID: {voice.id}, Languages: {voice.languages}")
            if 'JA' in voice.languages or 'JA-JP' in voice.id:
                engine.setProperty('voice', voice.id)
                break

    # Text to be spoken
    text_to_speak = text

    # Speak the text
    # engine.say(text_to_speak)
    engine.save_to_file(text_to_speak, audio_path)
    engine.runAndWait()