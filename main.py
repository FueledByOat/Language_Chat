# --- Core FastAPI & Python Imports ---
import os
import time
import uuid
import logging
import asyncio
import base64
from io import BytesIO
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

# --- FastAPI Imports ---
from fastapi import (
    BackgroundTasks,
    FastAPI,
    Request,
    HTTPException,
    File,
    UploadFile,
    Form,
    Path as FastAPIPath,  # Renamed to avoid conflict with `pathlib.Path`
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    FileResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# --- External Libraries ---
import uvicorn
import httpx  # For async HTTP requests (replaces `requests`)
import aiofiles  # For async file operations
from PIL import Image, ImageDraw
from transformers import pipeline

# --- Local Service Imports ---
import audio_io.audio_io as audio_service
import language_model.multilingual_model as llm_service
import translation.translator as translation_service
import translation.whisper_transcribe_claude as transcription_service
import utils.helper as utils
from config import Config
from app.services.nlp import NLPService
from app.services.vocab import VocabService
from constants.scenarios import SCENARIOS


# ==============================================================================
# 0. Configuration and Logging
# ==============================================================================

# Setup logging (same as your original)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Directory for serving HTML templates
templates = Jinja2Templates(directory="templates")
models: Dict[str, Any] = {}
http_client = httpx.AsyncClient(timeout=20.0, follow_redirects=True)
SUPPORTED_LANGUAGES = {"chinese", "japanese"}
nlp_service = NLPService()
vocab_service = VocabService()


def _get_enriched_tokens(
    text: str, language: str, session_id: str
) -> List[Dict[str, Any]]:
    """Helper to tokenize and fetch SRS levels."""
    enriched_tokens = []
    try:
        if language == "japanese":
            raw_tokens = nlp_service.process_japanese(text)
        elif language == "chinese":
            raw_tokens = nlp_service.process_chinese(text)
        else:
            raw_tokens = []

        for t in raw_tokens:
            level = vocab_service.get_user_word_level(session_id, t["base"], language)
            enriched_tokens.append(
                TokenData(
                    surface=t["surface"],
                    reading=t["reading"],
                    base_form=t["base"],
                    srs_level=level,
                ).dict()
            )
    except Exception as e:
        logger.error(f"Tokenization failed: {e}")
    return enriched_tokens


# Simple in-memory session store: { "session_id": [ {"role":..., "content":...} ] }
# In production, use Redis or a Database.
scenario_sessions: Dict[str, List[Dict[str, str]]] = {}
translation_cache: Dict[str, Dict[str, str]] = {}
cache_lock = asyncio.Lock()

# ==============================================================================
# 1. Pydantic Models (for Request/Response Validation)
# ==============================================================================


class TextChatRequest(BaseModel):
    """Pydantic model for the /api/text-chat request body."""

    message: str
    language: str


class TextChatResponse(BaseModel):
    """Pydantic model for the /api/text-chat response."""

    translatedUserText: str
    botResponse: str
    botResponseEnglish: str
    audioId: str


class VoiceChatResponse(TextChatResponse):
    """Pydantic model for the /api/voice-chat response."""

    transcribedText: str


class ImageGuessResponse(BaseModel):
    image: str  # Base64 string (original image, no boxes needed for roleplay)
    answer_text: str  # The text response in target language (CN/JP)
    audio_url: str  # URL/Path to the generated TTS audio


class ErrorResponse(BaseModel):
    """A standard error response."""

    error: str


class TokenData(BaseModel):
    """Represents a single word/character with learning data."""

    surface: str  # The word as displayed (e.g., "猫")
    reading: str  # Pinyin or Furigana (e.g., "neko")
    base_form: str  # Dictionary form for DB lookup
    srs_level: int = 0  # 0=New, 1-3=Learning, 4=Mastered
    pos: Optional[str] = None


# --- UPDATED RESPONSE MODEL ---
class ChatResponse(BaseModel):
    """
    Unified response model replacing TextChatResponse/VoiceChatResponse.
    It carries both raw text (for TTS/History) and tokens (for UI).
    """

    messageId: str
    audioId: Optional[str] = None

    # Text Data
    userText: str
    translatedUserText: Optional[str] = None

    botResponse: str  # Raw string (legacy support)
    botResponseEnglish: str

    # The New Smart Transcript Data
    botTokens: List[TokenData] = []


class VocabUpdateRequest(BaseModel):
    word_base: str
    language: str
    new_level: int
    user_id: str = "default_user"


# ==============================================================================
# 2. Lifespan Event (Model Loading & Cleanup)
# ==============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events.
    Loads models on startup and cleans up on shutdown.
    Replaces `_initialize_services` and `_cleanup_startup`.
    """
    # === Startup ===
    logger.info("Application startup...")

    # 1. Run startup cleanup
    try:
        await asyncio.to_thread(utils.cleanup)
        logger.info("Startup cleanup completed successfully")
    except Exception as e:
        logger.error(f"Startup cleanup failed: {e}", exc_info=True)

    # 2. Ensure audio directory exists
    os.makedirs(Config.AUDIO_DIR, exist_ok=True)

    # 2. Load Models (Independently!)

    # --- Load Language Model ---
    try:
        logger.info("Loading language model...")
        models["language_model"] = await asyncio.to_thread(
            llm_service.MultilingualModel
        )
    except Exception as e:
        logger.critical(f"❌ Language Model FAILED to load: {e}")

    # --- Load Transcription Model ---
    try:
        logger.info("Loading transcription model...")
        models["transcription_model"] = await asyncio.to_thread(
            transcription_service.SpeechTranscriber
        )
    except Exception as e:
        logger.critical(f"❌ Transcription Model FAILED to load: {e}")

    # --- Load Translator ---
    try:
        logger.info("Initializing translator...")
        models["translator"] = await asyncio.to_thread(translation_service.Translator)
    except Exception as e:
        logger.critical(f"❌ Translator FAILED to load: {e}")

    logger.info(
        "Startup sequence complete. Checking active models: " + ", ".join(models.keys())
    )

    yield

    # === Shutdown ===
    logger.info("Application shutdown...")
    models.clear()
    # if torch.cuda.is_available():
    #     torch.cuda.empty_cache()
    await http_client.aclose()
    logger.info("Cleanup complete. Exiting.")


# ==============================================================================
# 3. FastAPI Application Instance
# ==============================================================================

app = FastAPI(
    title="Language Learning App",
    description="API for language learning with text, voice, and images.",
    version="0.6.0 (FastAPI)",
    lifespan=lifespan,
)

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ==============================================================================
# 4. Async Helper Functions (Converted from class methods)
# ==============================================================================
# These helpers now contain all the core logic, converted to be async.


def _is_supported_language(language: str) -> bool:
    """Check if the language is supported."""
    return language in SUPPORTED_LANGUAGES


def _is_valid_audio_id(audio_id: str) -> bool:
    """Validate audio ID to prevent directory traversal attacks."""
    if not audio_id:
        return False
    if ".." in audio_id or "/" in audio_id or "\\" in audio_id:
        return False
    # Check for UUID (or fallback for cached keys)
    try:
        uuid.UUID(audio_id)
        return True
    except ValueError:
        return audio_id.replace("_", "").replace("-", "").isalnum()


async def run_translation_task(
    user_text: str, bot_response: str, language: str, message_id: str
):
    """
    Runs in the background. Translates text and saves it to the cache.
    FIXED: Use translate_to_english() instead of translate()
    """
    try:
        logger.info(f"Starting background translation for message {message_id}")

        # Run translations concurrently
        # FIXED: Changed from translate() to translate_to_english()
        results = await asyncio.gather(
            asyncio.to_thread(
                models["translator"].translate_to_english, user_text, language
            ),
            asyncio.to_thread(
                models["translator"].translate_to_english, bot_response, language
            ),
            return_exceptions=True,  # Capture exceptions instead of failing immediately
        )

        # Check for errors in results
        user_translation = results[0]
        bot_translation = results[1]

        if isinstance(user_translation, Exception):
            logger.error(f"Error translating user text: {user_translation}")
            user_translation = "(Translation failed)"

        if isinstance(bot_translation, Exception):
            logger.error(f"Error translating bot text: {bot_translation}")
            bot_translation = "(Translation failed)"

        # Store result in our cache
        translation_cache[message_id] = {
            "user_english": user_translation,
            "bot_english": bot_translation,
        }

        logger.info(f"Translations cached for message {message_id}")

    except Exception as e:
        logger.error(
            f"Background translation failed for message {message_id}: {e}",
            exc_info=True,
        )
        # Store a fallback in cache so the endpoint doesn't hang
        translation_cache[message_id] = {
            "user_english": "(Translation unavailable)",
            "bot_english": "(Translation unavailable)",
        }


async def _save_uploaded_audio_async(audio_file: UploadFile) -> str:
    """
    Save uploaded audio file with a unique filename using aiofiles.
    Enhanced with better error handling and validation.
    """
    audio_id = str(uuid.uuid4())
    audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.wav")

    try:
        # Ensure directory exists
        os.makedirs(Config.AUDIO_DIR, exist_ok=True)

        # Reset file pointer to beginning
        await audio_file.seek(0)

        bytes_written = 0
        async with aiofiles.open(audio_path, "wb") as f:
            while content := await audio_file.read(1024 * 1024):  # Read in 1MB chunks
                await f.write(content)
                bytes_written += len(content)

        logger.info(f"Saved audio file: {audio_path} ({bytes_written} bytes)")

        # Validate file was written
        if bytes_written == 0:
            raise ValueError("Audio file is empty")

        return audio_path

    except Exception as e:
        # Clean up partial file if it exists
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except:
                pass
        logger.error(f"Failed to save uploaded audio file: {e}", exc_info=True)
        raise ValueError(f"Failed to save audio file: {str(e)}")


async def _process_text_conversation_async(
    user_message: str, language: str, session_id: str = "default"
) -> Dict[str, Any]:
    # 1. Generate bot response
    try:
        bot_response = await asyncio.to_thread(
            models["language_model"].generate_response,
            user_message,
            language,
            use_history=False,
        )
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        bot_response = "Error generating response."

    # 2. Tokenize (Using the new helper)
    bot_tokens = _get_enriched_tokens(bot_response, language, session_id)

    # 3. Existing Concurrent Tasks (TTS & Translation)
    audio_id = str(uuid.uuid4())
    audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")

    try:
        results = await asyncio.gather(
            asyncio.to_thread(
                models["translator"].translate_to_english, user_message, language
            ),
            asyncio.to_thread(
                models["translator"].translate_to_english, bot_response, language
            ),
            asyncio.to_thread(
                audio_service.speak,
                audio_path=audio_path,
                text=bot_response,
                language=language,
            ),
        )
        translated_user_text = results[0]
        bot_response_english = results[1]

    except Exception as e:
        logger.error(f"Translation/TTS failed: {e}")
        translated_user_text = "(Error)"
        bot_response_english = "(Error)"
        audio_id = ""

    return {
        "userText": user_message,
        "translatedUserText": translated_user_text,
        "botResponse": bot_response,
        "botTokens": bot_tokens,  # Included!
        "botResponseEnglish": bot_response_english,
        "audioId": audio_id,
    }


async def _process_voice_conversation_async(
    audio_file: UploadFile, language: str
) -> Dict[str, Any]:
    """Async version of _process_voice_conversation with better error handling."""
    input_audio_path = None
    try:
        # 1. Save uploaded audio file (async)
        input_audio_path = await _save_uploaded_audio_async(audio_file)

        # Log file details for debugging
        logger.info(
            f"Audio file saved: {input_audio_path}, size: {os.path.getsize(input_audio_path)} bytes"
        )

        # 2. Transcribe audio (CPU-bound, run in thread)
        transcribed_text = await asyncio.to_thread(
            models["transcription_model"].transcribe_audio,
            audio_file=input_audio_path,
            language=language,
        )

        # Better error handling for empty transcription
        if not transcribed_text or not transcribed_text.strip():
            logger.warning(f"Empty transcription for file: {input_audio_path}")
            # Check if audio file is valid
            file_size = os.path.getsize(input_audio_path)
            if file_size < 1000:  # Less than 1KB is likely too small
                raise ValueError(
                    f"Audio file too small ({file_size} bytes). Please record a longer message."
                )
            else:
                raise ValueError(
                    "Could not transcribe audio. Please speak clearly and try again."
                )

        logger.info(f"Transcription successful: {transcribed_text[:50]}...")

        # 3. Process as text conversation (already async)
        result = await _process_text_conversation_async(transcribed_text, language)

        # 4. Add transcription to result
        result["transcribedText"] = transcribed_text
        return result

    except ValueError as e:
        # Re-raise ValueError with user-friendly message
        logger.error(f"Transcription validation error: {e}")
        raise
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected error in voice processing: {e}", exc_info=True)
        raise ValueError(
            "An error occurred while processing your voice message. Please try again."
        )
    finally:
        # 5. Clean up uploaded audio file
        if input_audio_path and os.path.exists(input_audio_path):
            try:
                # Run cleanup in a thread to avoid blocking
                await asyncio.to_thread(os.remove, input_audio_path)
                logger.debug(f"Cleaned up audio file: {input_audio_path}")
            except OSError as e:
                logger.warning(f"Failed to clean up audio file {input_audio_path}: {e}")


async def _fetch_image_async(image_url: str) -> Image.Image:
    """Fetch image from URL and convert to PIL Image."""
    try:
        response = await http_client.get(image_url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        logger.error(f"Failed to fetch image from {image_url}: {e}")
        raise


async def _fetch_random_image_async() -> Optional[str]:
    """Gets a random image URL, resolving redirects."""
    try:
        response = await http_client.get("https://picsum.photos/400/400")
        return str(response.url)
    except httpx.RequestError as e:
        logger.warning(f"Failed to fetch random image: {e}")
        return None


async def _get_or_create_cached_audio_async(
    cache_key: str, text: str, language: str
) -> str:
    """Async version of _get_or_create_cached_audio."""
    safe_key = "".join(x for x in cache_key if x.isalnum() or x in "_-")
    audio_path = os.path.join(Config.AUDIO_DIR, f"{safe_key}.mp3")

    # Use aiofiles to check existence async
    try:
        async with aiofiles.open(audio_path, "rb"):
            pass  # File exists
    except FileNotFoundError:
        # File doesn't exist, create it in a thread
        try:
            await asyncio.to_thread(
                audio_service.speak, audio_path=audio_path, text=text, language=language
            )
        except Exception as e:
            logger.error(f"Failed to generate cached audio: {e}")

    return audio_path


async def _process_scenario_conversation_async(
    audio_file: Optional[UploadFile],
    text_input: Optional[str],
    language: str,
    scenario_key: str,
    session_id: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    Handles the full loop: Text/Audio -> Text -> LLM (w/ Scenario Prompt & Memory) -> Audio
    """
    input_audio_path = None
    user_text = ""

    # 1. Validation
    if scenario_key not in SCENARIOS:
        raise ValueError("Invalid scenario")

    scenario_prompt = SCENARIOS[scenario_key]["prompt"]

    # 2. Determine User Input (Text vs Audio)
    if text_input and text_input.strip():
        # Case A: User typed text
        user_text = text_input
    elif audio_file:
        # Case B: User sent audio -> Transcribe it
        try:
            input_audio_path = await _save_uploaded_audio_async(audio_file)
            user_text = await asyncio.to_thread(
                models["transcription_model"].transcribe_audio,
                audio_file=input_audio_path,
                language=language,
            )
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise ValueError("Could not transcribe audio.")
    else:
        raise ValueError("No input provided (text or audio required).")

    if not user_text:
        raise ValueError("Input resulted in empty text.")

    # 3. Initialize Session if not exists
    if session_id not in scenario_sessions:
        scenario_sessions[session_id] = []

    current_history = scenario_sessions[session_id]

    try:
        # 4. Generate Response with Memory and Scenario Prompt
        bot_response = await asyncio.to_thread(
            models["language_model"].generate_response,
            user_message=user_text,
            language=language,
            use_history=False,  # We manually inject history below
            external_history=current_history,  # Pass the session specific history
            system_prompt_override=scenario_prompt,
        )
        # Generate Tokens for Smart Transcript
        bot_tokens = _get_enriched_tokens(bot_response, language, session_id)
        # -----------------------------

        # 5. Update Session Memory
        scenario_sessions[session_id].append({"role": "user", "content": user_text})
        scenario_sessions[session_id].append(
            {"role": "assistant", "content": bot_response}
        )

        # Limit memory... (keep existing logic)
        if len(scenario_sessions[session_id]) > 10:
            scenario_sessions[session_id] = scenario_sessions[session_id][-10:]

        message_id = str(uuid.uuid4())
        audio_id = str(uuid.uuid4())
        audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")

        # 6. Translate & TTS
        # FIRE AND FORGET Translation
        background_tasks.add_task(
            run_translation_task, user_text, bot_response, language, message_id
        )

        results = await asyncio.gather(
            asyncio.to_thread(
                models["translator"].translate_to_english, user_text, language
            ),
            asyncio.to_thread(
                models["translator"].translate_to_english, bot_response, language
            ),
            asyncio.to_thread(
                audio_service.speak,
                audio_path=audio_path,
                text=bot_response,
                language=language,
            ),
        )

        return {
            # Map 'transcribedText' to 'userText' for consistency with ChatResponse model
            "userText": user_text,
            "translatedUserText": results[0],
            "botResponse": bot_response,
            "botTokens": bot_tokens,  # <--- Return the tokens
            "botResponseEnglish": results[1],
            "audioId": audio_id,
            "messageId": message_id,
        }

    finally:
        if input_audio_path and os.path.exists(input_audio_path):
            await asyncio.to_thread(os.remove, input_audio_path)


# ==============================================================================
# 5. Route Handlers - HTML Pages
# ==============================================================================


@app.get("/", response_class=HTMLResponse, summary="Home Page", name="home")
async def home(request: Request):
    """Render the main home page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get(
    "/chinese", response_class=HTMLResponse, summary="Chinese Page", name="chinese"
)
async def chinese_page(request: Request):
    """Render the Chinese language learning page."""
    return templates.TemplateResponse("chinese.html", {"request": request})


@app.get(
    "/japanese", response_class=HTMLResponse, summary="Japanese Page", name="japanese"
)
async def japanese_page(request: Request):
    """Render the Japanese language learning page."""
    return templates.TemplateResponse("japanese.html", {"request": request})


@app.get(
    "/{language}/image", response_class=HTMLResponse, name="language_image"
)  # <--- ADD THIS NAME
async def language_image_page(request: Request, language: str):
    if not _is_supported_language(language):
        raise HTTPException(status_code=404)

    # Pre-fetch a random image URL to serve
    img_url = await _fetch_random_image_async()

    return templates.TemplateResponse(
        f"{language}_image.html",
        {"request": request, "img_file": img_url, "language": language},
    )


@app.get("/{language}/scenario", response_class=HTMLResponse)
async def scenario_page(request: Request, language: str):
    """Render the scenario selection page."""
    if not _is_supported_language(language):
        raise HTTPException(status_code=404, detail="Language not supported")

    return templates.TemplateResponse(
        "scenario.html",
        {"request": request, "language": language, "scenarios": SCENARIOS},
    )


# ==============================================================================
# 6. Route Handlers - API Endpoints
# ==============================================================================


async def _translate_and_cache(
    message_id: str,
    user_text: str,
    bot_text: str,
    source_lang: str,
    target_lang: str = "english",
):
    """
    Background task to translate texts and cache them.
    FIXED: Uses translate_to_english() method.
    """
    try:
        logger.info(f"Starting background translation for message {message_id}")

        # Run translations concurrently
        # FIXED: Use translate_to_english instead of translate
        results = await asyncio.gather(
            asyncio.to_thread(
                models["translator"].translate_to_english, user_text, source_lang
            ),
            asyncio.to_thread(
                models["translator"].translate_to_english, bot_text, source_lang
            ),
            return_exceptions=True,  # Don't let one failure break both
        )

        # Extract results with error handling
        user_translation = results[0]
        bot_translation = results[1]

        if isinstance(user_translation, Exception):
            logger.error(f"Error translating user text: {user_translation}")
            user_translation = "(Translation failed)"

        if isinstance(bot_translation, Exception):
            logger.error(f"Error translating bot text: {bot_translation}")
            bot_translation = "(Translation failed)"

        # Cache the translations
        translation_cache[message_id] = {
            "user_english": user_translation,
            "bot_english": bot_translation,
        }

        logger.info(f"Translations cached for message {message_id}")

    except Exception as e:
        logger.error(
            f"Background translation failed for message {message_id}: {e}",
            exc_info=True,
        )
        # Store fallback so the frontend doesn't hang
        translation_cache[message_id] = {
            "user_english": "(Translation unavailable)",
            "bot_english": "(Translation unavailable)",
        }


@app.post(
    "/api/text-chat",
    response_model=ChatResponse,
    responses={503: {"model": ErrorResponse}},
    summary="Text Chat Endpoint",
)
async def text_chat(
    background_tasks: BackgroundTasks,
    language: str = Form(...),
    text: str = Form(...),
    session_id: str = Form(default="default_user"),
):
    """Handle text-based chat API requests."""
    if "language_model" not in models or "translator" not in models:
        raise HTTPException(status_code=503, detail="Chat services are not available.")
    if not _is_supported_language(language):
        raise HTTPException(status_code=400, detail="Unsupported language")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        # Generate unique message ID
        message_id = str(uuid.uuid4())

        # Call the updated processor
        result = await _process_text_conversation_async(text, language, session_id)

        # Add message ID
        result["messageId"] = str(uuid.uuid4())

        # Start background translation task
        asyncio.create_task(
            _translate_and_cache(
                message_id=message_id,
                user_text=result.get("transcribedText", ""),  # User's spoken text
                bot_text=result.get("botResponse", ""),
                source_lang=language,
                target_lang="english",
            )
        )

        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in text_chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post(
    "/api/voice-chat",
    response_model=ChatResponse,  # <--- CHANGED from VoiceChatResponse
    responses={503: {"model": ErrorResponse}},
    summary="Voice Chat Endpoint",
)
async def voice_chat(language: str = Form(...), audio: UploadFile = File(...)):
    """Handle voice-based chat API requests."""
    if "transcription_model" not in models or "language_model" not in models:
        raise HTTPException(status_code=503, detail="Voice services are not available.")
    if not _is_supported_language(language):
        raise HTTPException(status_code=400, detail="Unsupported language")
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file provided")
    try:
        # Generate unique message ID
        message_id = str(uuid.uuid4())

        result = await _process_voice_conversation_async(audio, language)

        # Add message_id to response
        result["messageId"] = message_id

        # Start background translation task
        asyncio.create_task(
            _translate_and_cache(
                message_id=message_id,
                user_text=result.get("transcribedText", ""),  # User's spoken text
                bot_text=result.get("botResponse", ""),  # Bot's response
                source_lang=language,
                target_lang="english",
            )
        )

        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in voice_chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/api/audio/{audio_id}",
    response_class=FileResponse,
    summary="Serve Audio File",
)
async def play_audio(
    audio_id: str = FastAPIPath(
        ..., title="Audio ID", description="The UUID or cache key of the audio file"
    ),
):
    """
    Serve audio files by ID.
    This is the BUG FIX: It *only* serves the file.
    """
    safe_id = "".join(x for x in audio_id if x.isalnum() or x in "_-")
    audio_path = os.path.join(Config.AUDIO_DIR, f"{safe_id}.mp3")

    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(audio_path, media_type="audio/mpeg")


@app.post("/api/image_guess", response_model=ImageGuessResponse)
async def image_guess(
    language: str = Form(...),
    image_url: str = Form(...),
    audio: UploadFile = File(...),
):
    if "vqa" not in models:
        raise HTTPException(status_code=503, detail="VQA service unavailable")

    try:
        result = await _process_image_guess_async(audio, language, image_url)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in image_guess: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_endpoint(
    background_tasks: BackgroundTasks,
    language: str = Form(...),
    session_id: str = Form(default=""),
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
):
    """
    Unified endpoint for chat (mirrors /api/scenario-chat structure).
    Accepts either audio or text input via FormData.
    """
    try:
        # Validate that we have at least one input
        if not audio and not text:
            raise HTTPException(
                status_code=400, detail="Either audio or text is required."
            )

        # Validate language
        if not _is_supported_language(language):
            raise HTTPException(status_code=400, detail="Unsupported language")

        # Generate unique message ID
        message_id = str(uuid.uuid4())

        # Process based on input type
        if audio:
            # Handle audio input
            result = await _process_voice_conversation_async(audio, language)
        else:
            # Handle text input
            result = await _process_text_conversation_async(text, language)

        # Add message_id to response
        result["messageId"] = message_id

        # Determine user text for translation
        user_text = result.get("transcribedText") if audio else text
        bot_text = result.get("botResponse", "")

        # Start background translation task
        asyncio.create_task(
            _translate_and_cache(
                message_id=message_id,
                user_text=user_text or "",
                bot_text=bot_text,
                source_lang=language,
                target_lang="english",
            )
        )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat endpoint failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scenario-chat")
async def scenario_chat_endpoint(
    background_tasks: BackgroundTasks,
    language: str = Form(...),
    scenario: str = Form(...),
    session_id: str = Form(...),
    audio: Optional[UploadFile] = File(None),  # Changed to Optional, default None
    text: Optional[str] = Form(None),  # Added Optional Text
):
    """Endpoint for scenario-based roleplay."""
    try:
        # Validate that we have at least one input
        if not audio and not text:
            raise HTTPException(
                status_code=400, detail="Either audio or text is required."
            )

        result = await _process_scenario_conversation_async(
            audio_file=audio,
            text_input=text,
            language=language,
            scenario_key=scenario,
            session_id=session_id,
            background_tasks=background_tasks,
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Scenario chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/vocab/update")
async def update_vocab_endpoint(data: VocabUpdateRequest):
    """Update the SRS level for a specific word."""
    try:
        vocab_service.update_word_level(
            user_id=data.user_id,
            word=data.word_base,
            language=data.language,
            new_level=data.new_level,
        )
        return JSONResponse({"status": "success", "level": data.new_level})
    except Exception as e:
        logger.error(f"Vocab update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/translate-word")
async def translate_word_endpoint(text: str = Form(...), language: str = Form(...)):
    """Helper to translate a single word for the modal."""
    if "translator" not in models:
        raise HTTPException(status_code=503, detail="Translator not ready")

    try:
        # Use existing translator service
        translation = await asyncio.to_thread(
            models["translator"].translate_to_english, text, language
        )
        return JSONResponse({"translation": translation})
    except Exception as e:
        logger.error(f"Word translation failed: {e}")
        return JSONResponse({"translation": "Definition not found"})


@app.get("/api/translation/{message_id}")
async def get_translation(message_id: str):
    if message_id in translation_cache:
        return JSONResponse(translation_cache[message_id])
    return JSONResponse({"status": "pending"}, status_code=202)


@app.post("/api/reset-session")
async def reset_session(session_id: str = Form(...)):
    """Clear memory for a specific session."""
    if session_id in scenario_sessions:
        del scenario_sessions[session_id]
    return JSONResponse(content={"status": "cleared"})


# ==============================================================================
# 7. Main Entry Point
# ==============================================================================

if __name__ == "__main__":
    """
    Run the application using Uvicorn.
    """
    logger.info("Starting Language Learning App (FastAPI)...")
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True,  # Enable auto-reload for development
        log_level="info",
        ssl_keyfile="certs/key.pem",
        ssl_certfile="certs/cert.pem",
    )
