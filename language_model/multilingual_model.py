import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import logging
from typing import Optional, List, Dict


class MultilingualModel:
    """
    A multilingual conversational model using Qwen2.5-1.5B-Instruct.

    Supports Chinese, Japanese, and other languages with proper device detection
    and graceful fallback for various hardware configurations.
    """

    SUPPORTED_LANGUAGES = {
        "chinese": "Mandarin Chinese",
        "japanese": "Japanese",
        "english": "English",
        "spanish": "Spanish",
        "french": "French",
        "german": "German",
        "korean": "Korean",
    }

    def __init__(self):
        """
        Initialize the Qwen 2.5 model with automatic device detection.

        Attempts to load the model in the most efficient format based on
        available hardware (CUDA GPU, Apple Silicon, or CPU).
        """
        self.logger = logging.getLogger(__name__)
        self.model_id = "Qwen/Qwen2.5-1.5B-Instruct"
        self.pipe = None
        self.tokenizer = None
        self.device = None
        self.conversation_history: List[Dict[str, str]] = []

        self._load_model()

    def _load_model(self):
        """Load the model with appropriate settings for available hardware."""
        try:
            # Detect device and set appropriate configuration
            device_config = self._detect_device()
            self.device = device_config["device"]

            self.logger.info(f"Loading model on {self.device}...")

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, trust_remote_code=True
            )

            # Load model with device-specific settings
            model = AutoModelForCausalLM.from_pretrained(
                self.model_id, **device_config["model_kwargs"], trust_remote_code=True
            )

            # Move model to device if not already there
            if device_config["device"] not in ["auto", -1]:
                model = model.to(self.device)

            # Create pipeline
            self.pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=self.tokenizer,
                # device=self.device if isinstance(self.device, int) else -1,
            )

            self.logger.info(
                f"✓ Model '{self.model_id}' loaded successfully on {self.device}"
            )
            self.logger.info(f"✓ Device configuration: {device_config['description']}")

        except ImportError as e:
            self.logger.error(
                f"Missing required library: {e}. "
                "Install with: pip install transformers torch accelerate"
            )
            raise
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}", exc_info=True)
            raise RuntimeError(f"Model initialization failed: {e}")

    def _detect_device(self) -> Dict:
        """
        Detect available hardware and return appropriate configuration.

        Returns:
            Dict with 'device', 'model_kwargs', and 'description'
        """
        # Check for CUDA GPU
        if torch.cuda.is_available():
            try:
                # Try 4-bit quantization (requires bitsandbytes on Linux)
                import bitsandbytes as bnb

                self.logger.info("CUDA GPU detected with bitsandbytes support")
                return {
                    "device": 0,
                    "model_kwargs": {
                        "load_in_4bit": True,
                        "device_map": "auto",
                    },
                    "description": "CUDA GPU with 4-bit quantization",
                }
            except ImportError:
                # Fallback to 16-bit on GPU
                self.logger.info("CUDA GPU detected (16-bit mode)")
                return {
                    "device": 0,
                    "model_kwargs": {
                        "torch_dtype": torch.float16,
                        "device_map": "auto",
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
                },
                "description": "Apple Silicon (MPS) with 16-bit precision",
            }

        # Fallback to CPU
        else:
            self.logger.warning("⚠ No GPU detected - using CPU (will be slow)")
            self.logger.warning("⚠ Expect 5-15 seconds per response")
            return {
                "device": -1,
                "model_kwargs": {
                    "torch_dtype": torch.float32,
                    "low_cpu_mem_usage": True,
                },
                "description": "CPU with 32-bit precision",
            }

    def generate_response(
        self,
        user_message: str,
        language: str,
        use_history: bool = False,
        max_tokens: int = 150,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a response in the target language.

        Args:
            user_message: The user's message (in target language or English)
            language: Target language code (e.g., 'chinese', 'japanese')
            use_history: Whether to include conversation history
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Bot's response in the target language

        Raises:
            ValueError: If language is not supported or message is empty
            RuntimeError: If model is not loaded
        """
        # Validation
        if not self.pipe:
            raise RuntimeError("Model is not loaded. Cannot generate response.")

        if not user_message or not user_message.strip():
            raise ValueError("User message cannot be empty")

        language_lower = language.lower()
        if language_lower not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Language '{language}' not supported. "
                f"Supported languages: {', '.join(self.SUPPORTED_LANGUAGES.keys())}"
            )

        target_language = self.SUPPORTED_LANGUAGES[language_lower]

        # Build conversation messages
        messages = self._build_messages(user_message, target_language, use_history)

        # Generate response
        try:
            self.logger.debug(f"Generating response in {target_language}")

            output = self.pipe(
                messages,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.9,
                return_full_text=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )

            # Extract response
            if not output or not isinstance(output, list) or len(output) == 0:
                raise RuntimeError("Model returned empty output")

            if "generated_text" not in output[0]:
                raise RuntimeError("Model output missing 'generated_text' field")

            bot_response = output[0]["generated_text"].strip()

            if not bot_response:
                raise RuntimeError("Model generated empty response")

            # Update conversation history
            if use_history:
                self.conversation_history.append(
                    {"role": "user", "content": user_message}
                )
                self.conversation_history.append(
                    {"role": "assistant", "content": bot_response}
                )

            self.logger.info(f"✓ Generated response ({len(bot_response)} chars)")
            return bot_response

        except Exception as e:
            self.logger.error(f"Error during generation: {e}", exc_info=True)
            raise RuntimeError(f"Failed to generate response: {e}")

    def _build_messages(
        self, user_message: str, target_language: str, use_history: bool
    ) -> List[Dict[str, str]]:
        """
        Build the message list for the model including system prompt.

        Args:
            user_message: The user's input
            target_language: Full language name (e.g., "Mandarin Chinese")
            use_history: Whether to include conversation history

        Returns:
            List of message dictionaries
        """
        # System prompt with clear instructions
        system_prompt = (
            f"You are a language learning assistant. The user is practicing {target_language}. "
            f"IMPORTANT: You MUST respond ONLY in {target_language}. "
            f"Keep responses natural, conversational, and appropriate for language learners. "
            f"Use simple to moderate vocabulary and grammar."
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history if requested
        if use_history and self.conversation_history:
            # Keep last 6 messages (3 exchanges) to avoid context overflow
            recent_history = self.conversation_history[-6:]
            messages.extend(recent_history)

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        return messages

    def clear_history(self):
        """Clear the conversation history."""
        self.conversation_history.clear()
        self.logger.info("Conversation history cleared")

    def get_model_info(self) -> Dict[str, any]:
        """
        Get information about the loaded model.

        Returns:
            Dictionary with model information
        """
        return {
            "model_id": self.model_id,
            "device": str(self.device),
            "is_loaded": self.pipe is not None,
            "supported_languages": list(self.SUPPORTED_LANGUAGES.keys()),
            "history_length": len(self.conversation_history),
        }

    def __del__(self):
        """Cleanup resources when object is destroyed."""
        if self.pipe is not None:
            self.logger.info("Cleaning up model resources")
            del self.pipe
            del self.tokenizer
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
