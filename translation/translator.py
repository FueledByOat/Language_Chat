import logging
from typing import Optional
from enum import Enum
from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound, RequestError


class SupportedLanguage(Enum):
    """Enumeration of supported languages with their Google Translate codes."""
    CHINESE = "zh-CN"
    JAPANESE = "ja"
    ENGLISH = "en"


class TranslationError(Exception):
    """Custom exception for translation-related errors."""
    pass


class Translator:
    """
    A robust translator class for handling bidirectional translation between English 
    and supported target languages using Google Translate.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the translator.
        
        Args:
            logger: Optional logger instance. If None, creates a default logger.
        """
        self.logger = logger or self._setup_logger()
        self._validate_translator_availability()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up a logger for the translator."""
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
    
    def _validate_translator_availability(self) -> None:
        """Validate that the translation service is available."""
        try:
            # Test with a simple translation
            GoogleTranslator(source='en', target='zh-CN').translate("test")
        except Exception as e:
            self.logger.warning(f"Translation service may be unavailable: {e}")
    
    def _get_language_code(self, language: str) -> str:
        """
        Get the language code for the specified language.
        
        Args:
            language: Language name (case-insensitive)
            
        Returns:
            Language code for Google Translate
            
        Raises:
            TranslationError: If language is not supported
        """
        language_lower = language.lower()
        language_mapping = {
            'chinese': SupportedLanguage.CHINESE.value,
            'japanese': SupportedLanguage.JAPANESE.value,
            'english': SupportedLanguage.ENGLISH.value
        }
        
        if language_lower not in language_mapping:
            supported = ', '.join(language_mapping.keys())
            raise TranslationError(f"Unsupported language '{language}'. Supported: {supported}")
        
        return language_mapping[language_lower]
    
    def translate_to_english(self, text: str, source_language: str = "chinese") -> str:
        """
        Translate text from a target language to English.
        
        Args:
            text: Text to translate
            source_language: Source language name (default: "chinese")
            
        Returns:
            Translated text in English
            
        Raises:
            TranslationError: If translation fails
            ValueError: If input text is empty
        """
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")
        
        try:
            source_code = self._get_language_code(source_language)
            
            if source_code == SupportedLanguage.ENGLISH.value:
                self.logger.info("Source language is already English, returning original text")
                return text
            
            translator = GoogleTranslator(source=source_code, target=SupportedLanguage.ENGLISH.value)
            translated = translator.translate(text.strip())
            
            self.logger.info(f"Translated from {source_language}: '{text}' -> '{translated}'")
            return translated
            
        except (TranslationNotFound, RequestError) as e:
            error_msg = f"Translation service error: {str(e)}"
            self.logger.error(error_msg)
            raise TranslationError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected translation error: {str(e)}"
            self.logger.error(error_msg)
            raise TranslationError(error_msg) from e
    
    def translate_from_english(self, text: str, target_language: str = "chinese") -> str:
        """
        Translate text from English to a target language.
        
        Args:
            text: English text to translate
            target_language: Target language name (default: "chinese")
            
        Returns:
            Translated text in target language
            
        Raises:
            TranslationError: If translation fails
            ValueError: If input text is empty
        """
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")
        
        try:
            target_code = self._get_language_code(target_language)
            
            if target_code == SupportedLanguage.ENGLISH.value:
                self.logger.info("Target language is already English, returning original text")
                return text
            
            translator = GoogleTranslator(source=SupportedLanguage.ENGLISH.value, target=target_code)
            translated = translator.translate(text.strip())
            
            self.logger.info(f"Translated to {target_language}: '{text}' -> '{translated}'")
            return translated
            
        except (TranslationNotFound, RequestError) as e:
            error_msg = f"Translation service error: {str(e)}"
            self.logger.error(error_msg)
            raise TranslationError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected translation error: {str(e)}"
            self.logger.error(error_msg)
            raise TranslationError(error_msg) from e


# Backward compatibility functions
_default_translator = Translator()

def translate_target_to_english(input_text: str, language: str = "chinese") -> str:
    """Legacy function for backward compatibility."""
    return _default_translator.translate_to_english(input_text, language)

def translate_english_to_target(output_text: str, language: str = "chinese") -> str:
    """Legacy function for backward compatibility."""
    return _default_translator.translate_from_english(output_text, language)