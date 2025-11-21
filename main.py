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
from vqa_model.vqa_service import VQAService
import utils.helper as utils
from config import Config


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

# This is a global "state" dictionary to hold our loaded models
# It will be populated by the `lifespan` event
models: Dict[str, Any] = {}

# Re-usable async HTTP client (replaces `requests`)
http_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

SUPPORTED_LANGUAGES = {"chinese", "japanese"}


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

    # 3. Load models (wrapped in to_thread to avoid blocking)
    try:
        # Load Detector
        # logger.info("Loading VQA Service (Phi-3-Vision)...")

        # # Define a helper to instantiate and load weights inside the thread
        # def _load_vqa_service():
        #     service = VQAService()
        #     service.load_model()
        #     return service

        # models["vqa"] = await asyncio.to_thread(_load_vqa_service)
        # logger.info("Successfully loaded VQA Service.")

        # Load Language Model
        logger.info("Loading language model...")
        models["language_model"] = await asyncio.to_thread(
            llm_service.MultilingualModel
        )
        logger.info(
            f"Successfully loaded language model: {models['language_model'].model_id}"
        )

        # Load Transcription Model
        logger.info("Loading transcription model...")
        models["transcription_model"] = await asyncio.to_thread(
            transcription_service.SpeechTranscriber
        )
        logger.info("Successfully loaded transcription model.")

        # Load Translator (as a singleton instance)
        logger.info("Initializing translator...")
        models["translator"] = await asyncio.to_thread(translation_service.Translator)
        logger.info("Successfully initialized translator.")

    except Exception as e:
        logger.critical(f"Failed to load critical models: {e}", exc_info=True)
        # Note: You might want to exit the app if models fail to load

    logger.info("All models loaded. Application is ready.")

    yield  # --- Application is now running ---

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


async def _save_uploaded_audio_async(audio_file: UploadFile) -> str:
    """
    Save uploaded audio file with a unique filename using aiofiles.
    """
    audio_id = str(uuid.uuid4())
    # Note: Your whisper pipeline might handle .webm, but your old code
    # saved as .wav. Sticking to .wav as per your old logic.
    audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.wav")

    try:
        async with aiofiles.open(audio_path, "wb") as f:
            while content := await audio_file.read(1024 * 1024):  # Read in 1MB chunks
                await f.write(content)
        return audio_path
    except Exception as e:
        logger.error(f"Failed to save uploaded audio file: {e}", exc_info=True)
        raise


async def _process_text_conversation_async(
    user_message: str, language: str
) -> Dict[str, Any]:
    """
    Async version of _process_text_conversation.
    Runs I/O-bound tasks concurrently.
    """
    # 1. Generate bot response (CPU-bound, run in thread)
    # This is the first blocking call, so we await it.
    try:
        bot_response = await asyncio.to_thread(
            models["language_model"].generate_response,
            user_message,
            language,
            use_history=False,
        )
    except Exception as e:
        logger.error(f"Language model generation failed: {e}", exc_info=True)
        bot_response = "Sorry, I had trouble generating a response."

    # 2. Concurrently run translation and TTS generation
    # These tasks can all run at the same time!
    audio_id = str(uuid.uuid4())
    audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")

    try:
        results = await asyncio.gather(
            # Task A: Translate user text (I/O-bound, run in thread)
            asyncio.to_thread(
                models["translator"].translate_to_english, user_message, language
            ),
            # Task B: Translate bot text (I/O-bound, run in thread)
            asyncio.to_thread(
                models["translator"].translate_to_english, bot_response, language
            ),
            # Task C: Generate audio (Blocking I/O, run in thread)
            asyncio.to_thread(
                audio_service.speak,
                audio_path=audio_path,
                text=bot_response,
                language=language,
            ),
        )

        # Unpack results
        translated_user_text = results[0]
        bot_response_english = results[1]
        # results[2] is for the audio task, which doesn't return anything

    except Exception as e:
        logger.error(f"Translation or TTS failed: {e}", exc_info=True)
        translated_user_text = "(Translation failed)"
        bot_response_english = "(Translation failed)"
        audio_id = ""  # No audio was generated

    # 4. Return the data structure
    return {
        "translatedUserText": f"[English translation: {translated_user_text}]",
        "botResponse": bot_response,
        "botResponseEnglish": bot_response_english,
        "audioId": audio_id,
    }


async def _process_voice_conversation_async(
    audio_file: UploadFile, language: str
) -> Dict[str, Any]:
    """Async version of _process_voice_conversation."""
    input_audio_path = None
    try:
        # 1. Save uploaded audio file (async)
        input_audio_path = await _save_uploaded_audio_async(audio_file)

        # 2. Transcribe audio (CPU-bound, run in thread)
        transcribed_text = await asyncio.to_thread(
            models["transcription_model"].transcribe_audio,
            audio_file=input_audio_path,
            language=language,
        )

        if not transcribed_text:
            raise ValueError("Transcription returned empty text.")

        # 3. Process as text conversation (already async)
        result = await _process_text_conversation_async(transcribed_text, language)

        # 4. Add transcription to result
        result["transcribedText"] = transcribed_text
        return result

    finally:
        # 5. Clean up uploaded audio file
        if input_audio_path and os.path.exists(input_audio_path):
            try:
                # Run cleanup in a thread to avoid blocking
                await asyncio.to_thread(os.remove, input_audio_path)
            except OSError as e:
                logger.warning(f"Failed to clean up audio file {input_audio_path}: {e}")


async def _fetch_image_async(image_url: str) -> Image.Image:
    """Async version of _fetch_image using httpx."""
    try:
        response = await http_client.get(image_url)
        response.raise_for_status()  # Raise exception for 4xx/5xx
        return Image.open(BytesIO(response.content))
    except Exception as e:
        logger.error(f"Failed to fetch image from {image_url}: {e}")
        raise


async def _query_vqa_async(image: Image.Image, question_en: str) -> str:
    """
    Runs the image and English question through Phi-3-Vision.
    """

    def _run_inference():
        # 1. Format the prompt for Roleplay
        # We instruct the model to be concise and helpful.
        prompt = f"<|user|>\n<|image_1|>\n{question_en}<|end|>\n<|assistant|>\n"

        # 2. Process Inputs
        inputs = models["vqa"]["processor"](prompt, [image], return_tensors="pt").to(
            "cuda"
        )

        # 3. Generate Response parameters
        generation_args = {
            "max_new_tokens": 100,
            "temperature": 0.7,
            "do_sample": True,
        }

        # 4. Generate
        generate_ids = models["vqa"]["model"].generate(
            **inputs,
            eos_token_id=models["vqa"]["processor"].tokenizer.eos_token_id,
            **generation_args,
        )

        # 5. Decode
        # Remove input tokens to get just the answer
        generate_ids = generate_ids[:, inputs["input_ids"].shape[1] :]
        response = models["vqa"]["processor"].batch_decode(
            generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        return response

    return await asyncio.to_thread(_run_inference)


async def _process_image_guess_async(
    audio_file: UploadFile, language: str, image_url: str
) -> Dict[str, Any]:
    """Async version of _process_image_guess using the VQA Service."""
    input_audio_path = None
    try:
        # 1. Setup: Save Audio & Fetch Image concurrently
        save_task = asyncio.create_task(_save_uploaded_audio_async(audio_file))
        fetch_task = asyncio.create_task(_fetch_image_async(image_url))

        input_audio_path = await save_task
        image = await fetch_task

        # 2. Transcribe User Audio (Native Language)
        # e.g. "Where is the red car?"
        user_text_native = await asyncio.to_thread(
            models["transcription_model"].transcribe_audio,
            audio_file=input_audio_path,
            language=language,
        )

        # 3. Translate User Question -> English
        # Phi-3-Vision works best in English
        user_text_en = await asyncio.to_thread(
            models["translator"].translate_to_english, user_text_native, language
        )

        # 4. VQA Inference (Using our new Service Wrapper)
        # We add a "persona" here to make the game fun
        prompt = f"You are a helpful language tutor. Briefly answer this question based on the image: {user_text_en}"

        #
        # This call goes to the Service Layer -> GPU
        vqa_answer_en = await _query_vqa_async(image, prompt)

        # 5. Translate Answer -> Native Language (Target Language)
        # e.g. "The red car is on the left." -> "红色的小车在左边。"
        vqa_answer_native = await asyncio.to_thread(
            models["translator"].translate_from_english, vqa_answer_en, language
        )

        # 6. Generate Audio Response (TTS)
        # Create a unique ID for caching
        import uuid

        audio_filename = f"response_{uuid.uuid4().hex}"

        # Assuming you have a TTS service or function
        audio_path = await _get_or_create_cached_audio_async(
            audio_filename, vqa_answer_native, language
        )

        audio_url = f"/api/audio/{audio_filename}"

        # 7. Return Data
        # We re-encode the image to base64 to ensure the frontend displays exactly what the model saw
        def _encode_image(img):
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")

        img_str = await asyncio.to_thread(_encode_image, image)

        return {
            "image": img_str,
            "answer_text": vqa_answer_native,
            "audio_url": audio_url,
        }

    finally:
        if input_audio_path and os.path.exists(input_audio_path):
            try:
                await asyncio.to_thread(os.remove, input_audio_path)
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")


async def _query_vqa_async(image: Image.Image, question_en: str) -> str:
    """
    Non-blocking wrapper for the VQA service.
    Runs the heavy GPU inference in a separate thread.
    """
    if "vqa" not in models:
        raise RuntimeError("VQA Model not loaded")

    # We use asyncio.to_thread to run the synchronous service method
    response = await asyncio.to_thread(
        models["vqa"].analyze_image, image=image, question_en=question_en
    )

    return response


async def _fetch_random_image_async() -> Optional[str]:
    """Async version of _fetch_random_image using httpx."""
    try:
        response = await http_client.get("https://picsum.photos/400/400")
        response.raise_for_status()
        return str(response.url)  # Get final URL after redirects
    except httpx.RequestError as e:
        logger.warning(f"Failed to fetch random image: {e}")
        return None


async def _get_or_create_cached_audio_async(
    cache_key: str, text: str, language: str
) -> str:
    """Async version of _get_or_create_cached_audio."""
    audio_path = os.path.join(Config.AUDIO_DIR, f"{cache_key}.mp3")

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
    "/{language}/image",
    response_class=HTMLResponse,
    summary="Image Game Page",
    name="language_image",
)
async def language_image_page(request: Request, language: str):
    """Render language-specific image recognition page."""
    if not _is_supported_language(language):
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )

    if "detector" not in models or "translator" not in models:
        return templates.TemplateResponse(
            "503.html", {"request": request}, status_code=503
        )

    try:
        # Generate welcome message and audio (concurrently)
        bot_response_task = asyncio.create_task(
            asyncio.to_thread(
                models["translator"].translate_from_english,
                "What do you see?",
                language,
            )
        )
        img_url_task = asyncio.create_task(_fetch_random_image_async())

        bot_response = await bot_response_task
        img_url = await img_url_task

        # This depends on bot_response, so it's awaited after
        await _get_or_create_cached_audio_async(
            f"{language}_image", bot_response, language
        )

        return templates.TemplateResponse(
            f"{language}_image.html",
            {"request": request, "img_file": img_url, "language": language},
        )
    except Exception as e:
        logger.error(f"Error in language_image_page: {e}", exc_info=True)
        return templates.TemplateResponse(
            "500.html", {"request": request}, status_code=500
        )


# ==============================================================================
# 6. Route Handlers - API Endpoints
# ==============================================================================


@app.post(
    "/api/text-chat",
    response_model=TextChatResponse,
    responses={503: {"model": ErrorResponse}},
    summary="Text Chat Endpoint",
)
async def text_chat(request: TextChatRequest):
    """Handle text-based chat API requests."""
    if "language_model" not in models or "translator" not in models:
        raise HTTPException(status_code=503, detail="Chat services are not available.")

    if not _is_supported_language(request.language):
        raise HTTPException(status_code=400, detail="Unsupported language")

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        result = await _process_text_conversation_async(
            request.message, request.language
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in text_chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post(
    "/api/voice-chat",
    response_model=VoiceChatResponse,
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
        result = await _process_voice_conversation_async(audio, language)
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
    if not _is_valid_audio_id(audio_id):
        raise HTTPException(status_code=400, detail="Invalid audio ID")

    audio_path = os.path.join(Config.AUDIO_DIR, f"{audio_id}.mp3")

    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(audio_path, media_type="audio/mpeg")


@app.post(
    "/api/image_guess",
    response_model=ImageGuessResponse,
    responses={503: {"model": ErrorResponse}},
    summary="Image Guess Endpoint",
)
async def image_guess(
    language: str = Form(...),
    image_url: str = Form(...),
    audio: UploadFile = File(...),
):
    """Handle image object detection based on voice input."""
    if "detector" not in models or "transcription_model" not in models:
        raise HTTPException(
            status_code=503, detail="Image recognition services are unavailable."
        )

    if not _is_supported_language(language):
        raise HTTPException(status_code=400, detail="Unsupported language")

    try:
        result = await _process_image_guess_async(audio, language, image_url)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in image_guess: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


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
