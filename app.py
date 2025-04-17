from flask import Flask, request, send_file, jsonify, render_template, send_from_directory
import os
import uuid
import pyttsx3
import audio_io
import audio_io.audio_io
import language_model
import language_model.language_model
import translation
import translation.translator
import translation.vosk_transcribe
import utils.helper
import time
from playsound3 import playsound
from transformers import pipeline
import skimage
import numpy as np
from PIL import Image
from PIL import ImageDraw, ImageFont
import base64
from io import BytesIO

# Import your existing chat model implementation
# from your_module import your_chat_function

# Delete all old audio files upon startup
utils.helper.cleanup()

# Intantiate App
app = Flask(__name__)

# Directory for audio files
AUDIO_DIR = 'audio'
os.makedirs(AUDIO_DIR, exist_ok=True)

# Initialize text-to-speech engine
engine = pyttsx3.init()

# Serve home page
@app.route('/')
def home():
    return render_template('index.html')

# Serve language-specific pages
@app.route('/chinese')
def chinese():
    return render_template('chinese.html')

@app.route('/japanese')
def japanese():
    return render_template('japanese.html')

@app.route('/chinese_image')
def chinese_image():
    # Load supporting libraries

    checkpoint = "google/owlv2-base-patch16-ensemble"
    global detector 
    detector = pipeline(model=checkpoint, task="zero-shot-object-detection")
    
    bot_response = translation.translator.translate_english_to_target("What do you see?", language = "chinese")
    audio_id = "chinese_image"
    audio_path = os.path.join(AUDIO_DIR, f"{audio_id}.mp3")
    audio_io.audio_io.speak(audio_path = audio_path, text = bot_response, language = "chinese")

    return render_template('chinese_image.html')

# API endpoint for text chat
@app.route('/api/text-chat', methods=['POST'])
def text_chat():
    data = request.json
    user_message = data.get('message', '')
    language = data.get('language', '')
    
    # Here you would call your existing chat model function
    # Replace the following lines with your actual implementation
    # translated_user_text = your_translation_function(user_message, 'english')
    # bot_response, bot_response_english = your_chat_function(user_message, language)
    translated_user_text = translation.translator.translate_target_to_english(user_message, language = language)
    bot_response_english = language_model.language_model.bot_response(translated_user_text)
    bot_response = translation.translator.translate_english_to_target(bot_response_english, language = language)
        
    # Placeholder responses for now
    if language == 'chinese':
        translated_user_text = f"[English translation: {translated_user_text}]"
        bot_response = bot_response
        bot_response_english = bot_response_english
    else:  # japanese
        translated_user_text = f"[English translation: {translated_user_text}]"
        bot_response = bot_response
        bot_response_english = bot_response_english
    
    # Generate speech and save audio file
    audio_id = str(uuid.uuid4())
    audio_path = os.path.join(AUDIO_DIR, f"{audio_id}.mp3")
    
    # Generate TTS file
    audio_io.audio_io.speak(audio_path = audio_path, text = bot_response, language = language)
    playsound(audio_path)


    return jsonify({
        'translatedUserText': translated_user_text,
        'botResponse': bot_response,
        'botResponseEnglish': bot_response_english,
        'audioId': audio_id
    })

# API endpoint for voice chat
@app.route('/api/voice-chat', methods=['POST'])
def voice_chat():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    language = request.form.get('language', '')
    
    # Generate a unique filename
    input_audio_id = str(uuid.uuid4())
    input_audio_path = os.path.join(AUDIO_DIR, f"{input_audio_id}.wav")  # Save as webm
    
    # Save the uploaded audio file

    audio_file.save(input_audio_path)

    try:
        transcribed_text = translation.vosk_transcribe.transcribe(file = input_audio_path, tl = language)
        translated_user_text = translation.translator.translate_target_to_english(transcribed_text, language = language)
        bot_response_english = language_model.language_model.bot_response(translated_user_text)
        bot_response = translation.translator.translate_english_to_target(bot_response_english, language = language)
        
        # Placeholder responses for now
        if language == 'chinese':
            transcribed_text = transcribed_text
            translated_user_text = f"[English translation: {translated_user_text}]"
            bot_response = bot_response
            bot_response_english = bot_response_english
        else:  # japanese
            transcribed_text = transcribed_text
            translated_user_text = f"[English translation: {translated_user_text}]"
            bot_response = bot_response
            bot_response_english = bot_response_english
        
        # Generate speech and save audio file
        audio_id = str(uuid.uuid4())
        audio_path = os.path.join(AUDIO_DIR, f"{audio_id}.mp3")
        
        # Generate TTS
        audio_io.audio_io.speak(audio_path = audio_path, text = bot_response, language = language)
        playsound(audio_path)

        return jsonify({
            'transcribedText': transcribed_text,
            'translatedUserText': translated_user_text,
            'botResponse': bot_response,
            'botResponseEnglish': bot_response_english,
            'audioId': audio_id
        })
        
    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

# API endpoint for playing audio
@app.route('/api/audio/<audio_id>')
def play_audio(audio_id):
    # Security check - validate audio_id to prevent path traversal
    if not audio_id or '..' in audio_id or '/' in audio_id:
        return jsonify({'error': 'Invalid audio ID'}), 400
    
    audio_path = os.path.join(AUDIO_DIR, f"{audio_id}.mp3")
    
    if not os.path.exists(audio_path):
        return jsonify({'error': 'Audio file not found'}), 404

    # This would trigger your existing code:
    playsound(audio_path)
    
    return send_from_directory(AUDIO_DIR, f"{audio_id}.mp3")

@app.route('/api/image_guess', methods=['POST'])
def image_guess():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    language = request.form.get('language', '')
    
    # Generate a unique filename
    input_audio_id = str(uuid.uuid4())
    input_audio_path = os.path.join(AUDIO_DIR, f"{input_audio_id}.wav")  # Save as webm
    
    # Save the uploaded audio file

    audio_file.save(input_audio_path)

    # Temproary Image File
    # Specify the path to the image file
    image_path = r"static\img\360_F_236992283_sNOxCVQeFLd5pdqaKGh8DRGMZy7P4XKm.jpg"

    # Open the image using Image.open()
    try:
        img = Image.open(image_path)
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

    try:
        transcribed_text = translation.vosk_transcribe.transcribe(file = input_audio_path, tl = language)
        translated_user_text = translation.translator.translate_target_to_english(transcribed_text, language = language)
        guesses = [translated_user_text]

        predictions = detector(
            img,
            candidate_labels=guesses)
        predictions = [pic for pic in predictions if pic['score'] > 0.15]
    
        draw = ImageDraw.Draw(img)
        for prediction in predictions:
            box = prediction["box"]
            label = prediction["label"]
            score = prediction["score"]
            
            xmin, ymin, xmax, ymax = box.values()
            draw.ellipse((xmin, 
                        ymin, 
                        xmax, 
                        ymax), outline="blue", width=3)
            draw.text((xmin, ymin), f"{label.title()}: {round(score,2)}", fill="blue")

        buffered = BytesIO()
        draw.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Return the image as a base64-encoded string
        return jsonify({'image': img_str})

    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

if __name__ == '__main__':
    app.run(debug=True, port=5170)