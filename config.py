# config.py (project root)
import logging
import os
from typing import Optional
from dotenv import load_dotenv
load_dotenv(dotenv_path="secrets.env")

class Config:
    """Configuration class for environment variables and settings."""
    AUDIO_DIR = os.getenv('AUDIO_DIR', 'audio')
    DETECTOR_CHECKPOINT = "google/owlv2-base-patch16-ensemble"
    LANGUAGE_MODEL_NAME = "microsoft/DialoGPT-medium"
    CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    IMAGE_SCORE_THRESHOLD = 0.15
    # Huggingface token
    HF_TOKEN = os.getenv('HF_TOKEN', "broken_hf_key")
    
# Set up logging configuration
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='language_chat.log', 
    filemode='a')