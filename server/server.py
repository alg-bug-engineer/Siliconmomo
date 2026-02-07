from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from pathlib import Path
import time
from typing import Optional

from config import (
    HOST, PORT, MAX_FILE_SIZE_MB,
    WHISPER_CPP_PATH, MODEL_PATH
)
from transcriber import WhisperTranscriber
from utils.audio_converter import AudioConverter
from utils.file_manager import TempFileManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Audio Transcription Service",
    description="Transcribe audio/video files using whisper.cpp",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
try:
    transcriber = WhisperTranscriber(
        whisper_cpp_path=WHISPER_CPP_PATH,
        model_path=MODEL_PATH
    )
    WHISPER_READY = True
    logger.info("Whisper transcriber initialized successfully")
except Exception as e:
    WHISPER_READY = False
    logger.error(f"Failed to initialize whisper: {e}")

audio_converter = AudioConverter()
file_manager = TempFileManager()

# File size limit in bytes
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if WHISPER_READY else "degraded",
        "whisper_ready": WHISPER_READY,
        "model_loaded": WHISPER_READY
    }


@app.get("/info")
async def get_info():
    """Get service information"""
    return {
        "model": "small",
        "whisper_version": "1.5.4",
        "supported_languages": ["zh", "en", "ja", "ko", "es", "fr", "de", "auto"],
        "max_file_size_mb": MAX_FILE_SIZE_MB
    }


@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    task: str = "transcribe"
):
    """
    Transcribe audio/video file.

    Args:
        file: Audio or video file
        language: Language code (optional, auto-detect if not provided)
        task: "transcribe" or "translate"

    Returns:
        JSON with transcription result
    """
    if not WHISPER_READY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Whisper service not ready"
        )

    request_id = file_manager.get_unique_filename()[:8]
    logger.info(f"[{request_id}] New transcription request: {file.filename}")

    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        logger.warning(f"[{request_id}] File too large: {file_size / 1024 / 1024:.2f}MB")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {MAX_FILE_SIZE_MB}MB limit"
        )

    logger.info(f"[{request_id}] File size: {file_size / 1024 / 1024:.2f}MB")

    start_time = time.time()

    try:
        # Save uploaded file
        upload_path = file_manager.get_temp_path(suffix=Path(file.filename).suffix)
        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)

        upload_time = time.time() - start_time
        logger.info(f"[{request_id}] Upload completed in {upload_time:.2f}s")

        # Convert to WAV
        convert_start = time.time()
        wav_path = file_manager.get_temp_path(suffix=".wav")

        try:
            audio_converter.convert_to_wav(str(upload_path), str(wav_path))
            convert_time = time.time() - convert_start
            logger.info(f"[{request_id}] Conversion completed in {convert_time:.2f}s")
        except Exception as e:
            logger.error(f"[{request_id}] Conversion failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio conversion failed: {str(e)}"
            )
        finally:
            # Clean up upload file
            upload_path.unlink(missing_ok=True)

        # Get audio duration
        try:
            duration = audio_converter.get_audio_duration(str(wav_path))
            logger.info(f"[{request_id}] Audio duration: {duration:.2f}s")
        except:
            duration = 0.0

        # Transcribe
        transcribe_start = time.time()
        try:
            result = transcriber.transcribe(
                str(wav_path),
                language=language,
                task=task
            )
            transcribe_time = time.time() - transcribe_start
            logger.info(f"[{request_id}] Transcription completed in {transcribe_time:.2f}s")
        except Exception as e:
            logger.error(f"[{request_id}] Transcription failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transcription failed: {str(e)}"
            )
        finally:
            # Clean up WAV file
            wav_path.unlink(missing_ok=True)

        total_time = time.time() - start_time

        # Build response
        response = {
            "text": result["text"],
            "language": result["language"],
            "duration": round(duration, 2),
            "processing_time": round(total_time, 2)
        }

        logger.info(
            f"[{request_id}] Request completed in {total_time:.2f}s "
            f"(upload: {upload_time:.2f}s, convert: {convert_time:.2f}s, "
            f"transcribe: {transcribe_time:.2f}s)"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.on_event("startup")
async def startup_event():
    """Run on server startup"""
    logger.info("Starting Audio Transcription Service")
    # Clean up old temp files
    file_manager.cleanup_expired_files()


@app.on_event("shutdown")
async def shutdown_event():
    """Run on server shutdown"""
    logger.info("Shutting down Audio Transcription Service")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
