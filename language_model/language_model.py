import logging
import torch
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
from transformers.utils import logging as transformers_logging


@dataclass
class ModelConfig:
    """Configuration class for language model parameters."""
    model_name: str = "microsoft/DialoGPT-medium"
    
    # Response length control
    max_length: int = 50  # Reduced from 1000 - controls max tokens in response
    min_length: int = 5   # Minimum response length to avoid single-word replies
    
    # Sampling parameters (for controlling randomness and quality)
    do_sample: bool = True          # Enable sampling (vs greedy decoding)
    temperature: float = 0.7        # Higher = more creative/random (0.1-1.0)
    top_k: int = 50                 # Only consider top K tokens (lower = more focused)
    top_p: float = 0.9              # Nucleus sampling - cumulative probability cutoff
    repetition_penalty: float = 1.2  # Penalize repeated phrases (1.0 = no penalty)
    
    # Model behavior
    num_return_sequences: int = 1
    pad_token_id: Optional[int] = None
    
    # History management
    max_context_length: int = 300   # Limit context to prevent overlong prompts
    early_stopping: bool = True     # Stop when EOS token is generated


class ConversationManager:
    """Manages conversation history and context."""
    
    def __init__(self, max_history_length: int = 5):
        """
        Initialize conversation manager.
        
        Args:
            max_history_length: Maximum number of conversation turns to keep
        """
        self.max_history_length = max_history_length
        self.conversation_history: List[Dict[str, str]] = []
    
    def add_turn(self, user_input: str, bot_response: str) -> None:
        """Add a conversation turn to history."""
        self.conversation_history.append({
            'user': user_input,
            'bot': bot_response
        })
        
        # Keep only recent history
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    def get_context_string(self) -> str:
        """Get conversation history as a context string."""
        context_parts = []
        for turn in self.conversation_history:
            context_parts.append(f"User: {turn['user']}")
            context_parts.append(f"Bot: {turn['bot']}")
        return " ".join(context_parts)
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()


class LanguageModel:
    """
    Enhanced language model class with conversation management and robust error handling.
    """
    
    def __init__(self, config: Optional[ModelConfig] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize the language model.
        
        Args:
            config: Model configuration. Uses default if None.
            logger: Logger instance. Creates default if None.
        """
        self.config = config or ModelConfig()
        self.logger = logger or self._setup_logger()
        self.conversation_manager = ConversationManager()
        
        # Suppress transformer logs
        transformers_logging.set_verbosity_error()
        
        self._load_model()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger for the language model."""
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
    
    def _load_model(self) -> None:
        """Load the pre-trained model and tokenizer."""
        try:
            self.logger.info(f"Loading model: {self.config.model_name}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                padding_side="left"
            )
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None
            )
            
            # Set pad token if not available
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                self.config.pad_token_id = self.tokenizer.eos_token_id
            
            self.logger.info("Model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load model: {str(e)}")
            raise RuntimeError(f"Model loading failed: {str(e)}") from e
    
    def generate_response(self, user_input: str, use_history: bool = True) -> str:
        """
        Generate a response to user input.
        
        Args:
            user_input: User's input text
            use_history: Whether to use conversation history for context
            
        Returns:
            Generated response text
            
        Raises:
            ValueError: If input is empty
            RuntimeError: If generation fails
        """
        if not user_input or not user_input.strip():
            raise ValueError("User input cannot be empty")
        
        try:
            # Prepare input with optional context (limit context length to prevent confusion)
            if use_history:
                context = self.conversation_manager.get_context_string()
                # Truncate context if too long to prevent model confusion
                if len(context) > self.config.max_context_length:
                    context = context[-self.config.max_context_length:]
                full_input = f"{context} User: {user_input.strip()}" if context else f"User: {user_input.strip()}"
            else:
                full_input = user_input.strip()
            
            # Tokenize input with length limits
            input_ids = self.tokenizer.encode(
                full_input + self.tokenizer.eos_token,
                return_tensors="pt",
                truncation=True,
                max_length=400  # Shorter context to reduce confusion
            )
            
            # Generate response with better control parameters
            generation_config = GenerationConfig(
                max_length=min(input_ids.shape[-1] + self.config.max_length, 
                              input_ids.shape[-1] + 100),  # Cap absolute max
                min_length=input_ids.shape[-1] + self.config.min_length,
                do_sample=self.config.do_sample,
                temperature=self.config.temperature,
                top_k=self.config.top_k,
                top_p=self.config.top_p,
                repetition_penalty=self.config.repetition_penalty,
                num_return_sequences=self.config.num_return_sequences,
                pad_token_id=self.config.pad_token_id or self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                early_stopping=self.config.early_stopping
            )
            
            with torch.no_grad():
                output_ids = self.model.generate(
                    input_ids,
                    generation_config=generation_config
                )
            
            # Decode response (exclude input tokens)
            response_ids = output_ids[:, input_ids.shape[-1]:]
            response_text = self.tokenizer.decode(
                response_ids[0],
                skip_special_tokens=True
            ).strip()
            
            # Handle empty responses
            if not response_text:
                response_text = "I'm not sure how to respond to that. Could you rephrase your question?"
            
            # Update conversation history
            if use_history:
                self.conversation_manager.add_turn(user_input.strip(), response_text)
            
            self.logger.info(f"Generated response for input: '{user_input[:50]}...'")
            return response_text
            
        except Exception as e:
            error_msg = f"Response generation failed: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def clear_conversation_history(self) -> None:
        """Clear the conversation history."""
        self.conversation_manager.clear_history()
        self.logger.info("Conversation history cleared")