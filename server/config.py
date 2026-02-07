import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
WHISPER_CPP_PATH = os.getenv(
    "WHISPER_CPP_PATH",
    str(BASE_DIR / "whisper.cpp" / "main")
)
MODEL_PATH = os.getenv(
    "MODEL_PATH",
    str(BASE_DIR / "whisper.cpp" / "models" / "ggml-small.bin")
)

# Server config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))

# Temp files
TEMP_DIR = BASE_DIR / "temp"
TEMP_FILE_EXPIRE_HOURS = int(os.getenv("TEMP_FILE_EXPIRE_HOURS", "1"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "transcription.log"

# Ensure directories exist
TEMP_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
