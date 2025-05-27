from flask import Flask, request, send_file, jsonify, render_template, send_from_directory
import os
import uuid
import logging
import audio_io
import audio_io.audio_io
import language_model
import language_model.language_model
import translation
import translation.translator
import translation.vosk_transcribe
import utils.helper
from playsound3 import playsound
from transformers import pipeline
from PIL import Image, ImageDraw
import base64
from io import BytesIO
import requests
from config import Config

logger = logging.getLogger(__name__)

# Delete all old audio files upon startup
utils.helper.cleanup()

# -------------------------------------
# Flask and Language Model setup and initialization
# -------------------------------------

app = Flask(__name__)

# Directory for audio files
os.makedirs(Config.AUDIO_DIR, exist_ok=True)

# Load Zero Shot Detector
try:
    DETECTOR = pipeline(model=Config.DETECTOR_CHECKPOINT, task="zero-shot-object-detection")
    app.logger.info(f"Successfully loaded detector model: {Config.DETECTOR_CHECKPOINT}")
except Exception as e:
    app.logger.error(f"Failed to load detector model: {e}", exc_info=True)
    DETECTOR = None # Or handle startup failure appropriately

# -------------------------------------
# Home Page Endpoints
# -------------------------------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chinese')
def chinese():
    return render_template('chinese.html')

@app.route('/japanese')
def japanese():
    return render_template('japanese.html')

# -------------------------------------
# Image Endpoint Consolidated
# -------------------------------------

@app.route('/<string:language>/image')
def language_image_page(language):
    if language not in ['chinese', 'japanese']:
        return "Language not supported", 404 # Or render an error template

    # Make sure DETECTOR is loaded (globally)
    if not DETECTOR:
         return "Object detection service is unavailable.", 503

    bot_response = translation.translator.translate_english_to_target(
        "What do you see?", language=language
    )
    # Consider if this audio needs to be unique per request or can be static
    audio_id = f"{language}_image"
    audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")

    # Potentially cache this audio generation
    if not os.path.exists(audio_path):
         audio_io.audio_io.speak(audio_path=audio_path, text=bot_response, language=language)

    try:
        r = requests.get("https://picsum.photos/400/400", timeout=10) # e.g., 10 seconds
        r.raise_for_status()
        img_file = r.url
    except requests.exceptions.Timeout:
        app.logger.warning("Timeout fetching image from picsum.photos")
        # Handle timeout, e.g., return a default image or error
    except requests.exceptions.HTTPError as errh:
        app.logger.error(f"Http Error: {errh}")
        # Handle HTTP error
    except requests.exceptions.RequestException as err:
        app.logger.error(f"Request Error: {err}")
        # Handle other request errors

    return render_template(f'{language}_image.html', img_file=img_file, language=language)

# -------------------------------------
# API Endpoints
# -------------------------------------

# API endpoint for text chat
@app.route('/api/text-chat', methods=['POST'])
def text_chat():
    data = request.json
    user_message = data.get('message', '')
    language = data.get('language', '')

    translated_user_text = translation.translator.translate_target_to_english(user_message, language = language)
    bot_response_english = language_model.language_model.bot_response(translated_user_text)
    bot_response = translation.translator.translate_english_to_target(bot_response_english, language = language)

    translated_user_text = f"[English translation: {translated_user_text}]"
    bot_response = bot_response
    bot_response_english = bot_response_english
    
    # Generate speech and save audio file
    audio_id = str(uuid.uuid4())
    audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")
    
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
    input_audio_path = os.path.join(Config.AUDIO_DIR, f"{input_audio_id}.wav")  # Save as webm
    
    # Save the uploaded audio file

    audio_file.save(input_audio_path)

    try:
        transcribed_text = translation.vosk_transcribe.transcribe(file = input_audio_path, tl = language)
        translated_user_text = translation.translator.translate_target_to_english(transcribed_text, language = language)
        bot_response_english = language_model.language_model.bot_response(translated_user_text)
        bot_response = translation.translator.translate_english_to_target(bot_response_english, language = language)
        
        transcribed_text = transcribed_text
        translated_user_text = f"[English translation: {translated_user_text}]"
        bot_response = bot_response
        bot_response_english = bot_response_english
        
        # Generate speech and save audio file
        audio_id = str(uuid.uuid4())
        audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")
        
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
    
    audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")
    
    if not os.path.exists(audio_path):
        return jsonify({'error': 'Audio file not found'}), 404

    # This would trigger your existing code:
    playsound(audio_path)
    
    return send_from_directory(Config.AUDIO_DIR, f"{audio_id}.mp3")

@app.route('/api/image_guess', methods=['POST'])
def image_guess():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    language = request.form.get('language', '')
    
    # Generate a unique filename
    input_audio_id = str(uuid.uuid4())
    input_audio_path = os.path.join(Config.AUDIO_DIR, f"{input_audio_id}.wav")
    
    # Save the uploaded audio file

    audio_file.save(input_audio_path)

    # Specify the path to the image file
    image_url = request.form.get("image_url")
    image_data = requests.get(image_url)

    # Open the image using Image.open()
    try:
        img = Image.open(BytesIO(image_data.content))
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_url}")
    except Exception as e:
        print(f"An error occurred: {e}")

    try:
        transcribed_text = translation.vosk_transcribe.transcribe(file = input_audio_path, tl = language)
        translated_user_text = translation.translator.translate_target_to_english(transcribed_text, language = language)
        guesses = [translated_user_text]

        predictions = DETECTOR(
            img,
            candidate_labels=guesses)
        predictions = [pic for pic in predictions if pic['score'] > Config.IMAGE_SCORE_THRESHOLD]
    
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
        img.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Return the image as a base64-encoded string
        return jsonify({'image': img_str})

    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

if __name__ == '__main__':
    app.run(debug=True, port=5170)