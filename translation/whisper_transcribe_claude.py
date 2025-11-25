import torch
from transformers import pipeline, AutoModelForSpeechSeq2Seq, AutoProcessor
import logging
from pathlib import Path
from typing import Optional, Dict, List
import numpy as np


class SpeechTranscriber:
    """
    A speech transcriber using OpenAI's Whisper model via Hugging Face.

    Supports multiple languages with automatic device detection and
    optimization for various hardware configurations.
    """

    SUPPORTED_LANGUAGES = {
        "chinese": {"code": "zh", "name": "Chinese"},
        "japanese": {"code": "ja", "name": "Japanese"},
        "english": {"code": "en", "name": "English"},
        "spanish": {"code": "es", "name": "Spanish"},
        "french": {"code": "fr", "name": "French"},
        "german": {"code": "de", "name": "German"},
        "korean": {"code": "ko", "name": "Korean"},
        "italian": {"code": "it", "name": "Italian"},
        "portuguese": {"code": "pt", "name": "Portuguese"},
        "russian": {"code": "ru", "name": "Russian"},
    }

    MODEL_SIZES = {
        "tiny": "openai/whisper-tiny",  # ~39M params, fastest
        "base": "openai/whisper-base",  # ~74M params, good balance
        "small": "openai/whisper-small",  # ~244M params, better accuracy
        "medium": "openai/whisper-medium",  # ~769M params, high accuracy
    }

    def __init__(self, model_size: str = "small", use_faster_whisper: bool = True):
        """
        Initialize the Whisper transcription pipeline.

        Args:
            model_size: Model size ('tiny', 'base', 'small', 'medium')
            use_faster_whisper: Use optimized version (requires faster-whisper package)
        """
        self.logger = logging.getLogger(__name__)
        self.pipe = None
        self.device = None
        self.model_size = model_size
        self.use_faster_whisper = use_faster_whisper

        # Validate model size
        if model_size not in self.MODEL_SIZES:
            self.logger.warning(
                f"Invalid model size '{model_size}'. Defaulting to 'base'. "
                f"Available: {list(self.MODEL_SIZES.keys())}"
            )
            self.model_size = "base"

        self.model_id = self.MODEL_SIZES[self.model_size]
        self._load_model()

    def _load_model(self):
        """Load the Whisper model with appropriate settings for available hardware."""
        try:
            # Detect device and get configuration
            device_config = self._detect_device()
            self.device = device_config["device"]

            self.logger.info(
                f"Loading Whisper {self.model_size} model on {self.device}..."
            )

            if self.use_faster_whisper:
                self._load_faster_whisper(device_config)
            else:
                self._load_standard_whisper(device_config)

            self.logger.info(f"✓ Whisper model '{self.model_id}' loaded successfully")
            self.logger.info(f"✓ Device: {device_config['description']}")

        except ImportError as e:
            self.logger.error(
                f"Missing required library: {e}. "
                "Install with: pip install transformers torch accelerate"
            )
            raise
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}", exc_info=True)
            raise RuntimeError(f"Model initialization failed: {e}")

    def _load_standard_whisper(self, device_config: Dict):
        """Load using standard transformers pipeline."""
        # Load model with optimizations
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_id, **device_config["model_kwargs"]
        )

        # Move to device
        if device_config["device"] != "cpu":
            model = model.to(self.device)

        processor = AutoProcessor.from_pretrained(self.model_id)

        # Create pipeline
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            device=self.device if self.device != "cpu" else -1,
            chunk_length_s=30,  # Process in 30-second chunks
            stride_length_s=5,  # 5-second overlap for better accuracy
        )

    def _load_faster_whisper(self, device_config: Dict):
        """Load using faster-whisper for optimized inference."""
        try:
            from faster_whisper import WhisperModel

            compute_type = (
                "float16" if "16-bit" in device_config["description"] else "int8"
            )
            device_type = "cuda" if "CUDA" in device_config["description"] else "cpu"

            self.pipe = WhisperModel(
                self.model_size,
                device=device_type,
                compute_type=compute_type,
            )
            self.logger.info("Using faster-whisper for optimized inference")

        except ImportError:
            self.logger.warning(
                "faster-whisper not available. Install with: pip install faster-whisper"
            )
            self.use_faster_whisper = False
            self._load_standard_whisper(device_config)

    def _detect_device(self) -> Dict:
        """
        Detect available hardware and return appropriate configuration.

        Returns:
            Dict with 'device', 'model_kwargs', and 'description'
        """
        # Check for CUDA GPU
        if torch.cuda.is_available():
            self.logger.info("CUDA GPU detected")
            return {
                "device": "cuda",
                "model_kwargs": {
                    "torch_dtype": torch.float16,
                    "low_cpu_mem_usage": True,
                    "use_safetensors": True,
                },
                "description": "CUDA GPU with 16-bit precision",
            }

        # Check for Apple Silicon (MPS)
        elif torch.backends.mps.is_available():
            self.logger.info("Apple Silicon (MPS) detected")
            return {
                "device": "mps",
                "model_kwargs": {
                    "torch_dtype": torch.float16,
                    "low_cpu_mem_usage": True,
                },
                "description": "Apple Silicon (MPS) with 16-bit precision",
            }

        # Fallback to CPU
        else:
            self.logger.warning("⚠ No GPU detected - using CPU")
            return {
                "device": "cpu",
                "model_kwargs": {
                    "torch_dtype": torch.float32,
                    "low_cpu_mem_usage": True,
                },
                "description": "CPU with 32-bit precision",
            }

    def transcribe_audio(
        self,
        audio_file: str,
        language: str,
        return_timestamps: bool = False,
        task: str = "transcribe",
    ) -> str:
        """
        Transcribe an audio file using Whisper.

        Args:
            audio_file: Path to audio file (supports wav, mp3, m4a, etc.)
            language: Target language ('chinese', 'japanese', etc.)
            return_timestamps: Whether to include word-level timestamps
            task: 'transcribe' or 'translate' (translate converts to English)

        Returns:
            Transcribed text as a string

        Raises:
            ValueError: If language not supported or file doesn't exist
            RuntimeError: If model is not loaded or transcription fails
        """
        # Validation
        if not self.pipe:
            raise RuntimeError("Transcription model is not loaded")

        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise ValueError(f"Audio file does not exist: {audio_file}")

        if not audio_path.suffix.lower() in [".wav", ".mp3", ".m4a", ".flac", ".ogg"]:
            self.logger.warning(
                f"Unusual audio format: {audio_path.suffix}. "
                "Whisper supports wav, mp3, m4a, flac, ogg"
            )

        # Get language code
        language_lower = language.lower()
        if language_lower not in self.SUPPORTED_LANGUAGES:
            # Try auto-detection
            self.logger.warning(
                f"Language '{language}' not in supported list. "
                "Attempting auto-detection."
            )
            lang_code = None
        else:
            lang_code = self.SUPPORTED_LANGUAGES[language_lower]["code"]

        # Perform transcription
        try:
            self.logger.debug(f"Transcribing '{audio_file}' (language: {language})")

            if self.use_faster_whisper and hasattr(self.pipe, "transcribe"):
                # faster-whisper has different API
                transcribed_text = self._transcribe_faster(audio_file, lang_code, task)
            else:
                # Standard transformers pipeline
                transcribed_text = self._transcribe_standard(
                    audio_file, lang_code, task, return_timestamps
                )

            if not transcribed_text or not transcribed_text.strip():
                self.logger.warning("Transcription resulted in empty text")
                return ""

            self.logger.info(
                f"✓ Transcribed {audio_path.name}: "
                f"{transcribed_text[:50]}{'...' if len(transcribed_text) > 50 else ''}"
            )

            return transcribed_text.strip()

        except Exception as e:
            self.logger.error(
                f"Error during transcription of '{audio_file}': {e}", exc_info=True
            )
            raise RuntimeError(f"Transcription failed: {e}")

    def _transcribe_standard(
        self,
        audio_file: str,
        lang_code: Optional[str],
        task: str,
        return_timestamps: bool,
    ) -> str:
        """Transcribe using standard transformers pipeline."""
        generate_kwargs = {"task": task}

        if lang_code:
            generate_kwargs["language"] = lang_code

        # Additional generation parameters for better quality
        generate_kwargs.update(
            {
                "num_beams": 1,  # Greedy decoding is faster
                "return_timestamps": return_timestamps,
            }
        )

        result = self.pipe(
            audio_file,
            generate_kwargs=generate_kwargs,
            return_timestamps=return_timestamps,
        )

        return result.get("text", "")

    def _transcribe_faster(
        self, audio_file: str, lang_code: Optional[str], task: str
    ) -> str:
        """Transcribe using faster-whisper."""
        segments, info = self.pipe.transcribe(
            audio_file,
            language=lang_code,
            task=task,
            beam_size=1,
            vad_filter=True,  # Voice activity detection
        )

        # Combine all segments
        transcribed_text = " ".join([segment.text for segment in segments])

        return transcribed_text

    def transcribe_with_segments(
        self, audio_file: str, language: str
    ) -> List[Dict[str, any]]:
        """
        Transcribe audio and return segments with timestamps.

        Useful for showing subtitles or analyzing speech patterns.

        Args:
            audio_file: Path to audio file
            language: Target language

        Returns:
            List of segments with 'text', 'start', 'end' keys
        """
        if not self.pipe:
            raise RuntimeError("Transcription model is not loaded")

        lang_code = self.SUPPORTED_LANGUAGES.get(language.lower(), {}).get("code")

        try:
            if self.use_faster_whisper:
                segments, _ = self.pipe.transcribe(
                    audio_file, language=lang_code, task="transcribe"
                )
                return [
                    {"text": seg.text, "start": seg.start, "end": seg.end}
                    for seg in segments
                ]
            else:
                result = self.pipe(
                    audio_file,
                    generate_kwargs={"language": lang_code, "task": "transcribe"},
                    return_timestamps=True,
                )

                # Extract chunks from result
                chunks = result.get("chunks", [])
                return [
                    {
                        "text": chunk["text"],
                        "start": chunk["timestamp"][0],
                        "end": chunk["timestamp"][1],
                    }
                    for chunk in chunks
                ]

        except Exception as e:
            self.logger.error(f"Error getting segments: {e}", exc_info=True)
            raise RuntimeError(f"Segmented transcription failed: {e}")

    def get_model_info(self) -> Dict[str, any]:
        """
        Get information about the loaded model.

        Returns:
            Dictionary with model information
        """
        return {
            "model_id": self.model_id,
            "model_size": self.model_size,
            "device": str(self.device),
            "is_loaded": self.pipe is not None,
            "supported_languages": list(self.SUPPORTED_LANGUAGES.keys()),
            "using_faster_whisper": self.use_faster_whisper,
        }

    def __del__(self):
        """Cleanup resources when object is destroyed."""
        if self.pipe is not None:
            self.logger.info("Cleaning up Whisper model resources")
            del self.pipe
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
