from flask import Flask, request, jsonify, render_template, send_from_directory
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

# Serve static files
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

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
        print(input_audio_path)
        transcribed_text = translation.vosk_transcribe.transcribe(file = input_audio_path, tl = language)
        translated_user_text = translation.translator.translate_target_to_english(transcribed_text, language = language)
        bot_response = language_model.language_model.bot_response(translated_user_text)
        bot_response_english = translation.translator.translate_english_to_target(bot_response, language = language)
        
        # Placeholder responses for now
        if language == 'chinese':
            transcribed_text = "这是用户说的中文"
            translated_user_text = "This is what the user said in Chinese"
            bot_response = "这是中文回复"
            bot_response_english = "This is the English response"
        else:  # japanese
            transcribed_text = "これは日本語のユーザー入力です"
            translated_user_text = "This is what the user said in Japanese"
            bot_response = "これは日本語の応答です"
            bot_response_english = "This is the English response"
        
        # Generate speech and save audio file
        output_audio_id = str(uuid.uuid4())
        output_audio_path = os.path.join(AUDIO_DIR, f"{output_audio_id}.wav")
        
        # Generate TTS
        audio_io.audio_io.speak(text = bot_response, language = language)
        
        return jsonify({
            'transcribedText': transcribed_text,
            'translatedUserText': translated_user_text,
            'botResponse': bot_response,
            'botResponseEnglish': bot_response_english,
            'audioId': output_audio_id
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

if __name__ == '__main__':
    app.run(debug=True, port=5170)