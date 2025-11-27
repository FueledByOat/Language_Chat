import torch
from transformers import pipeline
import logging


class SpeechTranscriber:
    """
    A speech transcriber using a local Whisper model from Hugging Face.

    This class is a drop-in replacement for the original Vosk-based
    SpeechTranscriber. It implements the same public methods.
    """

    def __init__(self):
        """
        Initialize the Whisper pipeline.

        This will download the model on first run and cache it.
        It automatically uses the GPU (cuda) if available.
        """
        self.logger = logging.getLogger(__name__)

        try:
            # Check for GPU
            device = "cuda:0" if torch.cuda.is_available() else "cpu"

            # --- MODEL CHOICE ---
            # 'openai/whisper-base' is small and fast.
            # 'openai/whisper-medium' is larger but more accurate.
            # Start with 'base' to ensure it works, then consider 'medium'.
            self.model_id = "openai/whisper-base"

            self.pipe = pipeline(
                "automatic-speech-recognition", model=self.model_id, device=device
            )

            self.logger.info(
                f"Whisper model '{self.model_id}' loaded successfully on {device}."
            )

            # Map your app's language names to Whisper's language codes
            self.lang_map = {"chinese": "zh", "japanese": "ja"}

        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}", exc_info=True)
            self.pipe = None
            self.lang_map = {}

    def transcribe_audio(self, audio_file: str, language: str) -> str:
        """
        Transcribes an audio file using the Whisper model.

        Args:
            audio_file: The file path to the audio file (e.g., '.../audio.wav').
            language: The target language ('chinese' or 'japanese').

        Returns:
            The transcribed text as a string.
        """
        if not self.pipe:
            self.logger.error("Transcription model is not loaded. Cannot transcribe.")
            return ""

        lang_code = self.lang_map.get(language.lower())

        if not lang_code:
            self.logger.warning(
                f"Unsupported language '{language}' for transcription. Defaulting to no language."
            )
            # Whisper can auto-detect, but providing the language is more reliable
            generate_kwargs = {"task": "transcribe"}
        else:
            generate_kwargs = {"language": lang_code, "task": "transcribe"}

        try:
            # The pipeline can accept a file path directly
            result = self.pipe(audio_file, generate_kwargs=generate_kwargs)

            transcribed_text = result.get("text", "").strip()
            self.logger.info(f"Transcribed '{audio_file}' to: {transcribed_text}")
            return transcribed_text

        except Exception as e:
            self.logger.error(f"Error during audio transcription: {e}", exc_info=True)
            return ""
