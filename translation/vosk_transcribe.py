"""
vosk_transcribe.py

This module provides a function to take a recorded file and transcribe the audio into the text of the target language.  Currently, this only support Chinese.  
"""

import json
from vosk import Model, KaldiRecognizer, SetLogLevel
import wave
import re

# Disable Vosk Logs
SetLogLevel(-1)

# Constants
# Path to the downloaded Vosk model
MODEL_PATH = "translation/vosk-model-small-cn-0.22"

# Path to the input WAV file
WAV_FILE_PATH = "human_input.wav"

# Load the Vosk model
MODEL = Model(MODEL_PATH)

def transcribe(model = MODEL, file = WAV_FILE_PATH):
    """
    Uses a vosk model to transcribe a recorded WAV file to text in the target language

    Parameters:
    model (vosk Model): vosk model loaded from files stored locally on the host machine.
    file (string): file location of the recorded audio from the user 

    Output:
    string:  the transcribed text in the target language 
    """
        # Open the WAV file
    with wave.open(file, "rb") as wf:
        # Check if the audio file has the correct parameters
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() not in [8000, 16000, 32000, 44100, 48000]:
            raise Exception("Audio file must be WAV format mono PCM.")

        # Create a Kaldi recognizer with the model and the sample rate
        recognizer = KaldiRecognizer(model, wf.getframerate())

        # Read the audio data and transcribe it
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if recognizer.AcceptWaveform(data):
                result = recognizer.Result()
                text = json.loads(result).get('text', '')

        # Final result
        final_result = recognizer.FinalResult()
        final_result_test = json.loads(final_result).get('text', '')

        if final_result_test != "":
            input_text = json.loads(final_result).get('text', '')
            input_text = re.sub(r"\s+", "", input_text, flags=re.UNICODE)
        else:
            input_text = re.sub(r"\s+", "", text, flags=re.UNICODE)

        print(f"Transcribed Text: {input_text}")

        return input_text