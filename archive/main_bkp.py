from googletrans import Translator
import json
import wave
from vosk import Model, KaldiRecognizer, SetLogLevel
import pyaudio
import re
import pyttsx3
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import logging

# Not sustainable but using this to suppresses console logs
logging.getLogger('transformers').setLevel(logging.ERROR)

# Disable Vosk Logs
SetLogLevel(-1)

# Step 0: Records Audio Sample

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 3

finish = "continue"

while finish.lower() != 'done':
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

        print('\nRecording...')
        try:
            while True:
                wf.writeframes(stream.read(CHUNK))
        except KeyboardInterrupt:
            pass
        
        print('Done')

        stream.close()
        p.terminate()


    # Step 1: Chinese Speech Recognition with Vosk

    # Path to the downloaded Vosk model
    model_path = "vosk-model-small-cn-0.22"

    # Path to the input WAV file
    wav_file_path = "human_input.wav"

    # Load the Vosk model
    model = Model(model_path)

    # Open the WAV file
    with wave.open(wav_file_path, "rb") as wf:
        # Check if the audio file has the correct parameters
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() not in [8000, 16000, 32000, 44100, 48000]:
            # print("Audio file must be WAV format mono PCM.")
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
                # print(result)
                text = json.loads(result).get('text', '')
                # print(f"Recognized text: {text}")

        # Final result
        final_result = recognizer.FinalResult()
        final_result_test = json.loads(final_result).get('text', '')

        if final_result_test != "":
            chinese_input_text = json.loads(final_result).get('text', '')
            chinese_input_text = re.sub(r"\s+", "", chinese_input_text, flags=re.UNICODE)
        else:
            chinese_input_text = re.sub(r"\s+", "", text, flags=re.UNICODE)

        print(f"Final recognized text: {chinese_input_text}")

    # Step 2: Translate from Chinese to English 

    # Initialize the translator
    translator = Translator()

    # Translate from Chinese to English
    translated = translator.translate(chinese_input_text, src='zh-cn', dest='en')
    print(f"Input: {translated.text}")  

    # Step 3

    # Load the pre-trained model and tokenizer
    # model_name = "microsoft/DialoGPT-small"
    model_name = "microsoft/DialoGPT-medium"
    model = AutoModelForCausalLM.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")


    # take user input
    text = translated.text

    # encode the input and add end of string token
    input_ids = tokenizer.encode(text + tokenizer.eos_token, return_tensors="pt")
    # concatenate new user input with chat history (if there is)
    # bot_input_ids = torch.cat([chat_history_ids, input_ids], dim=-1) if step > 0 else input_ids
    bot_input_ids = input_ids
    # generate a bot response
    chat_history_ids = model.generate(
        bot_input_ids,
        max_length=1000,
        do_sample=True,
        top_k=100,
        temperature=0.63,
        pad_token_id=tokenizer.eos_token_id
    )
    #print the output
    output_text = tokenizer.decode(chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)
    
    print(f"DialoGPT: {output_text}")

    # Step 4:  Translate back to Chinese

    # Translate from English to Chinese
    translated_to_zh = translator.translate(output_text, src='en', dest='zh-cn')
    print(translated_to_zh.text)  

    # Step 5: Translate reply back to Chinese 

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
    text_to_speak = translated_to_zh.text

    # Speak the text
    engine.say(text_to_speak)
    engine.runAndWait()

    # New line
    finish = input("Type done to end: ")