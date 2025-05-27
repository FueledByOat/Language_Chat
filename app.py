"""
Flask Language Learning Application

A web application that provides language learning capabilities through text and voice chat,
image recognition, and translation features for Chinese and Japanese languages.

Author: Charlie Smith
Version: 0.5.1
"""

import os
import uuid
import logging
from typing import Optional, Dict, Any, Tuple
from io import BytesIO
import base64

from flask import Flask, request, send_file, jsonify, render_template, send_from_directory
import requests
from PIL import Image, ImageDraw
from transformers import pipeline
from playsound3 import playsound

# Local imports
import audio_io.audio_io as audio_service
import language_model.language_model as llm_service
import translation.translator as translation_service
import translation.vosk_transcribe as transcription_service
import utils.helper as utils
from config import Config


class LanguageLearningApp:
    """Main application class for the Language Learning Flask app."""
    
    SUPPORTED_LANGUAGES = {'chinese', 'japanese'}
    
    def __init__(self):
        """Initialize the Flask application and configure logging."""
        self.app = Flask(__name__)
        self.language_model = None
        self.detector = None
        self.transcription_model = None
        self._setup_logging()
        self._initialize_services()
        self._register_routes()
        self._cleanup_startup()
    
    def _setup_logging(self) -> None:
        """Configure application logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def _cleanup_startup(self) -> None:
        """Clean up old files on application startup."""
        try:
            utils.cleanup()
            self.logger.info("Startup cleanup completed successfully")
        except Exception as e:
            self.logger.error(f"Startup cleanup failed: {e}", exc_info=True)
    
    def _initialize_services(self) -> None:
        """Initialize external services and models."""
        # Ensure audio directory exists
        os.makedirs(Config.AUDIO_DIR, exist_ok=True)
        
        # Initialize object detection model
        self._load_detector_model()
        # Initialize language model
        self._load_language_model()
        # Initialize transcription model
        self._load_transcription_model()

    def _load_transcription_model(self) -> None:
        """Load the language transcription model."""
        try:
            self.transcription_model = transcription_service.SpeechTranscriber()
            self.logger.info(f"Successfully loaded transcription model.")
        except Exception as e:
            self.logger.error(f"Failed to load transcription model: {e}", exc_info=True)
            self.transcription_model = None
    
    def _load_language_model(self) -> None:
        """Load the conversational language model."""
        try:
            self.language_model = llm_service.LanguageModel()
            self.logger.info(f"Successfully loaded language model: {self.language_model.config.model_name}")
        except Exception as e:
            self.logger.error(f"Failed to load language model: {e}", exc_info=True)
            self.language_model = None

    def _load_detector_model(self) -> None:
        """Load the zero-shot object detection model."""
        try:
            self.detector = pipeline(
                model=Config.DETECTOR_CHECKPOINT, 
                task="zero-shot-object-detection"
            )
            self.logger.info(f"Successfully loaded detector model: {Config.DETECTOR_CHECKPOINT}")
        except Exception as e:
            self.logger.error(f"Failed to load detector model: {e}", exc_info=True)
            self.detector = None
    
    def _register_routes(self) -> None:
        """Register all Flask routes."""
        # Main page routes
        self.app.add_url_rule('/', 'home', self.home)
        self.app.add_url_rule('/chinese', 'chinese', self.chinese_page)
        self.app.add_url_rule('/japanese', 'japanese', self.japanese_page)
        
        # Dynamic language-specific routes
        self.app.add_url_rule(
            '/<string:language>/image', 
            'language_image_page', 
            self.language_image_page
        )
        
        # API routes
        self.app.add_url_rule(
            '/api/text-chat', 
            'text_chat', 
            self.text_chat, 
            methods=['POST']
        )
        self.app.add_url_rule(
            '/api/voice-chat', 
            'voice_chat', 
            self.voice_chat, 
            methods=['POST']
        )
        self.app.add_url_rule(
            '/api/audio/<audio_id>', 
            'play_audio', 
            self.play_audio
        )
        self.app.add_url_rule(
            '/api/image_guess', 
            'image_guess', 
            self.image_guess, 
            methods=['POST']
        )
    
    # ================================
    # Route Handlers - Main Pages
    # ================================
    
    def home(self):
        """Render the main home page."""
        return render_template('index.html')
    
    def chinese_page(self):
        """Render the Chinese language learning page."""
        return render_template('chinese.html')
    
    def japanese_page(self):
        """Render the Japanese language learning page."""
        return render_template('japanese.html')
    
    def language_image_page(self, language: str):
        """
        Render language-specific image recognition page.
        
        Args:
            language: Target language ('chinese' or 'japanese')
            
        Returns:
            Rendered template or error response
        """
        if not self._is_supported_language(language):
            return "Language not supported", 404
        
        if not self.detector:
            return "Object detection service is unavailable.", 503
        
        try:
            # Generate welcome message in target language
            bot_response = translation_service.translate_english_to_target(
                "What do you see?", language=language
            )
            
            # Generate or retrieve cached audio
            audio_path = self._get_or_create_cached_audio(
                f"{language}_image", bot_response, language
            )
            
            # Fetch random image
            img_url = self._fetch_random_image()
            
            return render_template(
                f'{language}_image.html', 
                img_file=img_url, 
                language=language
            )
            
        except Exception as e:
            self.logger.error(f"Error in language_image_page: {e}", exc_info=True)
            return "Internal server error", 500
    
    # ================================
    # Route Handlers - API Endpoints
    # ================================
    
    def text_chat(self):
        """
        Handle text-based chat API requests.
        
        Expected JSON payload:
        {
            "message": "user message in target language",
            "language": "chinese" or "japanese"
        }
        
        Returns:
            JSON response with translations and audio ID
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            user_message = data.get('message', '').strip()
            language = data.get('language', '').strip()
            
            if not user_message or not language:
                return jsonify({'error': 'Message and language are required'}), 400
            
            if not self._is_supported_language(language):
                return jsonify({'error': 'Unsupported language'}), 400
            
            # Process the conversation
            result = self._process_text_conversation(user_message, language)
            
            return jsonify(result)
            
        except Exception as e:
            self.logger.error(f"Error in text_chat: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
    
    def voice_chat(self):
        """
        Handle voice-based chat API requests.
        
        Expected form data:
        - audio: audio file
        - language: target language
        
        Returns:
            JSON response with transcription, translations, and audio ID
        """
        try:
            if 'audio' not in request.files:
                return jsonify({'error': 'No audio file provided'}), 400
            
            audio_file = request.files['audio']
            language = request.form.get('language', '').strip()
            
            if not language or not self._is_supported_language(language):
                return jsonify({'error': 'Valid language parameter required'}), 400
            
            if audio_file.filename == '':
                return jsonify({'error': 'No audio file selected'}), 400
            
            # Process the voice conversation
            result = self._process_voice_conversation(audio_file, language)
            
            return jsonify(result)
            
        except Exception as e:
            self.logger.error(f"Error in voice_chat: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
    
    def play_audio(self, audio_id: str):
        """
        Serve audio files by ID.
        
        Args:
            audio_id: Unique identifier for the audio file
            
        Returns:
            Audio file or error response
        """
        try:
            # Security validation
            if not self._is_valid_audio_id(audio_id):
                return jsonify({'error': 'Invalid audio ID'}), 400
            
            audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")
            
            if not os.path.exists(audio_path):
                return jsonify({'error': 'Audio file not found'}), 404
            
            # Play audio locally (consider removing in production)
            try:
                playsound(audio_path)
            except Exception as e:
                self.logger.warning(f"Failed to play audio locally: {e}")
            
            return send_from_directory(Config.AUDIO_DIR, f"{audio_id}.mp3")
            
        except Exception as e:
            self.logger.error(f"Error in play_audio: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
    
    def image_guess(self):
        """
        Handle image object detection based on voice input.
        
        Expected form data:
        - audio: audio file with object guess
        - language: target language
        - image_url: URL of image to analyze
        
        Returns:
            JSON response with processed image (base64 encoded)
        """
        try:
            if 'audio' not in request.files:
                return jsonify({'error': 'No audio file provided'}), 400
            
            audio_file = request.files['audio']
            language = request.form.get('language', '').strip()
            image_url = request.form.get('image_url', '').strip()
            
            if not all([language, image_url]):
                return jsonify({'error': 'Language and image_url are required'}), 400
            
            if not self._is_supported_language(language):
                return jsonify({'error': 'Unsupported language'}), 400
            
            if not self.detector:
                return jsonify({'error': 'Object detection service unavailable'}), 503
            
            # Process the image guess
            result = self._process_image_guess(audio_file, language, image_url)
            
            return jsonify(result)
            
        except Exception as e:
            self.logger.error(f"Error in image_guess: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
    
    # ================================
    # Helper Methods
    # ================================
    
    def _is_supported_language(self, language: str) -> bool:
        """Check if the language is supported by the application."""
        return language in self.SUPPORTED_LANGUAGES
    
    def _is_valid_audio_id(self, audio_id: str) -> bool:
        """Validate audio ID to prevent directory traversal attacks."""
        if not audio_id:
            return False
        
        # Check for path traversal attempts
        if '..' in audio_id or '/' in audio_id or '\\' in audio_id:
            return False
        
        # Validate UUID format (optional but recommended)
        try:
            uuid.UUID(audio_id)
            return True
        except ValueError:
            # Allow non-UUID audio IDs for cached files
            return audio_id.replace('_', '').replace('-', '').isalnum()
    
    def _fetch_random_image(self) -> Optional[str]:
        """
        Fetch a random image URL from picsum.photos.
        
        Returns:
            Image URL or None if fetch fails
        """
        try:
            response = requests.get(
                "https://picsum.photos/400/400", 
                timeout=10,
                allow_redirects=True
            )
            response.raise_for_status()
            return response.url
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Failed to fetch random image: {e}")
            return None
    
    def _get_or_create_cached_audio(
        self, 
        cache_key: str, 
        text: str, 
        language: str
    ) -> str:
        """
        Get cached audio file or create new one.
        
        Args:
            cache_key: Unique cache identifier
            text: Text to convert to speech
            language: Target language
            
        Returns:
            Path to audio file
        """
        audio_path = os.path.join(Config.AUDIO_DIR, f"{cache_key}.mp3")
        
        if not os.path.exists(audio_path):
            try:
                audio_service.speak(
                    audio_path=audio_path, 
                    text=text, 
                    language=language
                )
            except Exception as e:
                self.logger.error(f"Failed to generate cached audio: {e}")
        
        return audio_path
    
    def _save_uploaded_audio(self, audio_file) -> str:
        """
        Save uploaded audio file with unique filename.
        
        Args:
            audio_file: Flask uploaded file object
            
        Returns:
            Path to saved audio file
        """
        audio_id = str(uuid.uuid4())
        audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.wav")
        audio_file.save(audio_path)
        return audio_path
    
    def _process_text_conversation(self, user_message: str, language: str) -> Dict[str, Any]:
        """
        Process a text-based conversation.
        
        Args:
            user_message: User's message in target language
            language: Target language code
            
        Returns:
            Dictionary with conversation results
        """
        # Translate user message to English
        translated_user_text = translation_service.translate_target_to_english(
            user_message, language=language
        )
        
        # Generate bot response in English
        bot_response_english = self.language_model.generate_response(translated_user_text, use_history=False)
        
        # Translate bot response to target language
        bot_response = translation_service.translate_english_to_target(
            bot_response_english, language=language
        )
        
        # Generate audio for bot response
        audio_id = str(uuid.uuid4())
        audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")
        
        try:
            audio_service.speak(
                audio_path=audio_path, 
                text=bot_response, 
                language=language
            )
            
            # Play audio locally (consider removing in production)
            playsound(audio_path)
            
        except Exception as e:
            self.logger.error(f"Failed to generate or play audio: {e}")
        
        return {
            'translatedUserText': f"[English translation: {translated_user_text}]",
            'botResponse': bot_response,
            'botResponseEnglish': bot_response_english,
            'audioId': audio_id
        }
    
    def _process_voice_conversation(self, audio_file, language: str) -> Dict[str, Any]:
        """
        Process a voice-based conversation.
        
        Args:
            audio_file: Uploaded audio file
            language: Target language code
            
        Returns:
            Dictionary with conversation results
        """
        # Save uploaded audio
        input_audio_path = self._save_uploaded_audio(audio_file)
        
        try:
            # Transcribe audio
            transcribed_text = self.transcription_model.transcribe_audio(
                audio_file=input_audio_path, 
                language=language
            )
            
            # Process as text conversation
            result = self._process_text_conversation(transcribed_text, language)
            
            # Add transcription to result
            result['transcribedText'] = transcribed_text
            
            return result
            
        finally:
            # Clean up uploaded audio file
            try:
                os.remove(input_audio_path)
            except OSError as e:
                self.logger.warning(f"Failed to clean up audio file {input_audio_path}: {e}")
    
    def _process_image_guess(
        self, 
        audio_file, 
        language: str, 
        image_url: str
    ) -> Dict[str, Any]:
        """
        Process image object detection based on voice input.
        
        Args:
            audio_file: Audio file with object guess
            language: Target language code
            image_url: URL of image to analyze
            
        Returns:
            Dictionary with processed image results
        """
        # Save and transcribe audio
        input_audio_path = self._save_uploaded_audio(audio_file)
        
        try:
            # Transcribe the guess
            transcribed_text = self.transcription_model.transcribe_audio(
                audio_file=input_audio_path, 
                language=language
            )
            
            # Translate to English for object detection
            translated_guess = translation_service.translate_target_to_english(
                transcribed_text, language=language
            )
            
            # Fetch and process image
            image = self._fetch_image(image_url)
            processed_image = self._detect_objects_in_image(image, [translated_guess])
            
            # Convert image to base64
            buffered = BytesIO()
            processed_image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            return {'image': img_str}
            
        finally:
            # Clean up uploaded audio file
            try:
                os.remove(input_audio_path)
            except OSError as e:
                self.logger.warning(f"Failed to clean up audio file {input_audio_path}: {e}")
    
    def _fetch_image(self, image_url: str) -> Image.Image:
        """
        Fetch image from URL.
        
        Args:
            image_url: URL of the image
            
        Returns:
            PIL Image object
            
        Raises:
            Exception: If image cannot be fetched or opened
        """
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        except Exception as e:
            self.logger.error(f"Failed to fetch image from {image_url}: {e}")
            raise
    
    def _detect_objects_in_image(
        self, 
        image: Image.Image, 
        candidate_labels: list
    ) -> Image.Image:
        """
        Perform object detection on image and draw bounding boxes.
        
        Args:
            image: PIL Image object
            candidate_labels: List of object labels to detect
            
        Returns:
            PIL Image with bounding boxes drawn
        """
        try:
            # Run object detection
            predictions = self.detector(image, candidate_labels=candidate_labels)
            
            # Filter predictions by confidence threshold
            high_confidence_predictions = [
                pred for pred in predictions 
                if pred['score'] > Config.IMAGE_SCORE_THRESHOLD
            ]
            
            # Draw bounding boxes
            draw = ImageDraw.Draw(image)
            for prediction in high_confidence_predictions:
                box = prediction["box"]
                label = prediction["label"]
                score = prediction["score"]
                
                xmin, ymin, xmax, ymax = box.values()
                
                # Draw bounding box
                draw.rectangle(
                    [xmin, ymin, xmax, ymax], 
                    outline="blue", 
                    width=3
                )
                
                # Draw label
                draw.text(
                    (xmin, ymin - 20), 
                    f"{label.title()}: {round(score, 2)}", 
                    fill="blue"
                )
            
            return image
            
        except Exception as e:
            self.logger.error(f"Object detection failed: {e}")
            return image  # Return original image if detection fails
    
    def run(self, debug: bool = True, port: int = 5170, host: str = '127.0.0.1') -> None:
        """
        Run the Flask application.
        
        Args:
            debug: Enable debug mode
            port: Port number to run on
            host: Host address to bind to
        """
        self.logger.info(f"Starting Language Learning App on {host}:{port}")
        self.app.run(debug=debug, port=port, host=host)


# ================================
# Application Factory Function
# ================================

def create_app() -> Flask:
    """
    Application factory function.
    
    Returns:
        Configured Flask application instance
    """
    app_instance = LanguageLearningApp()
    return app_instance.app


# ================================
# Main Entry Point
# ================================

if __name__ == '__main__':
    try:
        app_instance = LanguageLearningApp()
        app_instance.run(debug=True, port=5170)
    except Exception as e:
        logging.error(f"Failed to start application: {e}", exc_info=True)
        raise