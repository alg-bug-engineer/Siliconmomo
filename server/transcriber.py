import subprocess
import logging
import re
from pathlib import Path
from typing import Dict, Optional
from config import WHISPER_CPP_PATH, MODEL_PATH

logger = logging.getLogger(__name__)

class WhisperTranscriber:
    """Transcribe audio using whisper.cpp"""

    def __init__(
        self,
        whisper_cpp_path: str = WHISPER_CPP_PATH,
        model_path: str = MODEL_PATH
    ):
        """
        Initialize transcriber and validate paths.

        Args:
            whisper_cpp_path: Path to whisper.cpp main executable
            model_path: Path to ggml model file

        Raises:
            FileNotFoundError: If whisper.cpp or model not found
        """
        self.whisper_cpp_path = Path(whisper_cpp_path)
        self.model_path = Path(model_path)

        if not self.whisper_cpp_path.exists():
            raise FileNotFoundError(
                f"whisper.cpp not found at {self.whisper_cpp_path}. "
                "Please compile whisper.cpp first."
            )

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {self.model_path}. "
                "Please download the model first."
            )

        logger.info(f"Initialized WhisperTranscriber with model: {self.model_path}")

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Dict[str, any]:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to 16kHz WAV file
            language: Language code (e.g., "zh", "en"). None for auto-detect.
            task: "transcribe" or "translate"

        Returns:
            Dict with keys: text, language, processing_time

        Raises:
            Exception: If transcription fails
        """
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Build whisper.cpp command
        cmd = [
            str(self.whisper_cpp_path),
            "-m", str(self.model_path),
            "-f", audio_path,
            "--output-txt",  # Output plain text
            "--no-timestamps",  # Don't output timestamps for cleaner text
        ]

        if language:
            cmd.extend(["-l", language])

        if task == "translate":
            cmd.append("--translate")

        logger.info(f"Running whisper.cpp: {' '.join(cmd)}")

        try:
            # Run whisper.cpp
            import time
            start_time = time.time()

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            processing_time = time.time() - start_time

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"whisper.cpp failed: {error_msg}")
                raise Exception(f"Transcription failed: {error_msg}")

            # Parse output
            output = result.stdout

            # Extract transcribed text (whisper.cpp outputs to stdout)
            # Format: "[LANGUAGE] text here"
            text = self._parse_output(output)
            detected_lang = self._detect_language(output)

            logger.info(f"Transcription completed in {processing_time:.2f}s")

            return {
                "text": text.strip(),
                "language": detected_lang or language or "unknown",
                "processing_time": round(processing_time, 2)
            }

        except subprocess.TimeoutExpired:
            logger.error("Transcription timeout")
            raise Exception("Transcription timeout (>5 minutes)")
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise

    def _parse_output(self, output: str) -> str:
        """
        Parse whisper.cpp output to extract text.

        Args:
            output: Raw stdout from whisper.cpp

        Returns:
            Extracted text
        """
        # whisper.cpp outputs format: [LANGUAGE] transcribed text
        # Remove language tag and clean up
        lines = output.split('\n')
        text_lines = []

        for line in lines:
            # Skip empty lines and progress indicators
            line = line.strip()
            if not line or line.startswith('['):
                continue
            text_lines.append(line)

        return ' '.join(text_lines)

    def _detect_language(self, output: str) -> Optional[str]:
        """
        Detect language from whisper.cpp output.

        Args:
            output: Raw stdout from whisper.cpp

        Returns:
            Language code or None
        """
        # Look for language detection in output
        # Format: "Detected language: Chinese"
        match = re.search(r'detected language:\s*(\w+)', output, re.IGNORECASE)
        if match:
            lang_name = match.group(1).lower()
            # Map common language names to codes
            lang_map = {
                'chinese': 'zh',
                'english': 'en',
                'japanese': 'ja',
                'korean': 'ko',
                'spanish': 'es',
                'french': 'fr',
                'german': 'de',
            }
            return lang_map.get(lang_name, lang_name)

        return None
