import json
import logging
import wave
import re
import os
from pathlib import Path
from typing import Optional, Union, Dict, Any
from enum import Enum
from dataclasses import dataclass
from vosk import Model, KaldiRecognizer, SetLogLevel


class TranscriptionLanguage(Enum):
    """Supported transcription languages."""
    CHINESE = "chinese"
    JAPANESE = "japanese"


@dataclass
class AudioConfig:
    """Audio file configuration and requirements."""
    required_channels: int = 1
    required_sample_width: int = 2
    supported_sample_rates: tuple = (8000, 16000, 32000, 44100, 48000)
    chunk_size: int = 4000


class TranscriptionError(Exception):
    """Custom exception for transcription-related errors."""
    pass


class SpeechTranscriber:
    """
    Enhanced speech transcription class using Vosk models with robust error handling 
    and audio validation.
    """
    
    def __init__(self, model_base_path: str = "translation", logger: Optional[logging.Logger] = None):
        """
        Initialize the speech transcriber.
        
        Args:
            model_base_path: Base path where Vosk models are stored
            logger: Optional logger instance
        """
        self.model_base_path = Path(model_base_path)
        self.logger = logger or self._setup_logger()
        self.audio_config = AudioConfig()
        
        # Disable Vosk logs
        SetLogLevel(-1)
        
        # Model paths
        self.model_paths = {
            TranscriptionLanguage.CHINESE: self.model_base_path / "vosk-model-small-cn-0.22",
            TranscriptionLanguage.JAPANESE: self.model_base_path / "vosk-model-small-ja-0.22"
        }
        
        # Cache for loaded models
        self._model_cache: Dict[TranscriptionLanguage, Model] = {}
        
        self._validate_model_availability()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger for the transcriber."""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def _validate_model_availability(self) -> None:
        """Validate that required models are available."""
        missing_models = []
        for language, model_path in self.model_paths.items():
            if not model_path.exists():
                missing_models.append(f"{language.value}: {model_path}")
        
        if missing_models:
            self.logger.warning(f"Missing model directories: {missing_models}")
    
    def _get_language_enum(self, language: str) -> TranscriptionLanguage:
        """
        Convert language string to enum.
        
        Args:
            language: Language string
            
        Returns:
            TranscriptionLanguage enum
            
        Raises:
            TranscriptionError: If language is not supported
        """
        language_lower = language.lower()
        for lang_enum in TranscriptionLanguage:
            if lang_enum.value == language_lower:
                return lang_enum
        
        supported = [lang.value for lang in TranscriptionLanguage]
        raise TranscriptionError(f"Unsupported language '{language}'. Supported: {supported}")
    
    def _load_model(self, language: TranscriptionLanguage) -> Model:
        """
        Load Vosk model for the specified language.
        
        Args:
            language: Target language enum
            
        Returns:
            Loaded Vosk model
            
        Raises:
            TranscriptionError: If model loading fails
        """
        if language in self._model_cache:
            return self._model_cache[language]
        
        model_path = self.model_paths[language]
        
        if not model_path.exists():
            raise TranscriptionError(f"Model not found: {model_path}")
        
        try:
            self.logger.info(f"Loading {language.value} model from {model_path}")
            model = Model(str(model_path))
            self._model_cache[language] = model
            self.logger.info(f"Successfully loaded {language.value} model")
            return model
            
        except Exception as e:
            error_msg = f"Failed to load {language.value} model: {str(e)}"
            self.logger.error(error_msg)
            raise TranscriptionError(error_msg) from e
    
    def _validate_audio_file(self, audio_file: Union[str, Path]) -> Path:
        """
        Validate audio file format and properties.
        
        Args:
            audio_file: Path to audio file
            
        Returns:
            Validated Path object
            
        Raises:
            TranscriptionError: If file is invalid
        """
        file_path = Path(audio_file)
        
        if not file_path.exists():
            raise TranscriptionError(f"Audio file not found: {file_path}")
        
        if not file_path.suffix.lower() == '.wav':
            raise TranscriptionError(f"Only WAV files are supported, got: {file_path.suffix}")
        
        try:
            with wave.open(str(file_path), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_rate = wf.getframerate()
                
                if channels != self.audio_config.required_channels:
                    raise TranscriptionError(
                        f"Audio must be mono (1 channel), got {channels} channels"
                    )
                
                if sample_width != self.audio_config.required_sample_width:
                    raise TranscriptionError(
                        f"Audio must be 16-bit (2 bytes per sample), got {sample_width} bytes"
                    )
                
                if frame_rate not in self.audio_config.supported_sample_rates:
                    raise TranscriptionError(
                        f"Unsupported sample rate {frame_rate}Hz. "
                        f"Supported: {self.audio_config.supported_sample_rates}"
                    )
                
                self.logger.debug(f"Audio validation passed: {channels}ch, {sample_width*8}bit, {frame_rate}Hz")
                
        except wave.Error as e:
            raise TranscriptionError(f"Invalid WAV file: {str(e)}") from e
        
        return file_path
    
    def _clean_transcription_text(self, text: str) -> str:
        """
        Clean and normalize transcribed text.
        
        Args:
            text: Raw transcribed text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove extra whitespace for Chinese/Japanese (they don't use spaces)
        cleaned = re.sub(r"\s+", "", text, flags=re.UNICODE)
        return cleaned.strip()
    
    def transcribe_audio(
        self,
        audio_file: Union[str, Path] = "human_input.wav",
        language: str = "chinese"
    ) -> str:
        """
        Transcribe audio file to text in the specified language.
        
        Args:
            audio_file: Path to the WAV audio file
            language: Target language for transcription
            
        Returns:
            Transcribed text in the target language
            
        Raises:
            TranscriptionError: If transcription fails
            ValueError: If parameters are invalid
        """
        try:
            # Validate inputs
            language_enum = self._get_language_enum(language)
            file_path = self._validate_audio_file(audio_file)
            
            # Load model
            model = self._load_model(language_enum)
            
            # Transcribe audio
            transcribed_text = self._perform_transcription(file_path, model)
            
            if not transcribed_text:
                self.logger.warning("No speech detected in audio file")
                return ""
            
            cleaned_text = self._clean_transcription_text(transcribed_text)
            self.logger.info(f"Transcribed ({language}): '{cleaned_text}'")
            
            return cleaned_text
            
        except TranscriptionError:
            raise
        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            self.logger.error(error_msg)
            raise TranscriptionError(error_msg) from e
    
    def _perform_transcription(self, audio_file: Path, model: Model) -> str:
        """
        Perform the actual audio transcription.
        
        Args:
            audio_file: Validated audio file path
            model: Loaded Vosk model
            
        Returns:
            Raw transcribed text
        """
        transcribed_segments = []
        final_result = ""
        
        try:
            with wave.open(str(audio_file), "rb") as wf:
                recognizer = KaldiRecognizer(model, wf.getframerate())
                
                # Process audio in chunks
                while True:
                    data = wf.readframes(self.audio_config.chunk_size)
                    if len(data) == 0:
                        break
                    
                    if recognizer.AcceptWaveform(data):
                        result = recognizer.Result()
                        result_data = json.loads(result)
                        text = result_data.get('text', '').strip()
                        if text:
                            transcribed_segments.append(text)
                
                # Get final result
                final_result_json = recognizer.FinalResult()
                final_result_data = json.loads(final_result_json)
                final_text = final_result_data.get('text', '').strip()
                
                # Combine results
                if final_text:
                    return final_text
                elif transcribed_segments:
                    return ' '.join(transcribed_segments)
                else:
                    return ""
                    
        except json.JSONDecodeError as e:
            raise TranscriptionError(f"Failed to parse transcription result: {str(e)}") from e
        except Exception as e:
            raise TranscriptionError(f"Audio processing failed: {str(e)}") from e