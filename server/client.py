import httpx
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class TranscriptionClient:
    """Python client for Audio Transcription Service"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize client.

        Args:
            base_url: Base URL of transcription service
        """
        self.base_url = base_url.rstrip('/')
        logger.info(f"Initialized TranscriptionClient for {self.base_url}")

    async def health_check(self) -> Dict:
        """
        Check service health.

        Returns:
            Health status dict
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    async def get_info(self) -> Dict:
        """
        Get service information.

        Returns:
            Service info dict
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/info")
            response.raise_for_status()
            return response.json()

    async def transcribe_async(
        self,
        file_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        timeout: float = 300.0
    ) -> Dict:
        """
        Transcribe audio file (async).

        Args:
            file_path: Path to audio/video file
            language: Language code (e.g., "zh", "en")
            task: "transcribe" or "translate"
            timeout: Request timeout in seconds

        Returns:
            Transcription result dict with keys: text, language, duration, processing_time

        Raises:
            FileNotFoundError: If file doesn't exist
            httpx.HTTPError: If request fails
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Transcribing {file_path}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                data = {}
                if language:
                    data["language"] = language
                if task != "transcribe":
                    data["task"] = task

                response = await client.post(
                    f"{self.base_url}/transcribe",
                    files=files,
                    data=data
                )
                response.raise_for_status()
                result = response.json()

        logger.info(f"Transcription completed: {len(result.get('text', ''))} chars")
        return result

    def transcribe(
        self,
        file_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        timeout: float = 300.0
    ) -> Dict:
        """
        Transcribe audio file (synchronous wrapper).

        Args:
            file_path: Path to audio/video file
            language: Language code (e.g., "zh", "en")
            task: "transcribe" or "translate"
            timeout: Request timeout in seconds

        Returns:
            Transcription result dict
        """
        import asyncio

        # Create event loop if none exists
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.transcribe_async(file_path, language, task, timeout)
        )


# Convenience function
def transcribe(
    file_path: str,
    base_url: str = "http://localhost:8000",
    language: Optional[str] = None
) -> str:
    """
    Convenience function to transcribe a file.

    Args:
        file_path: Path to audio/video file
        base_url: Service URL
        language: Language code

    Returns:
        Transcribed text
    """
    client = TranscriptionClient(base_url)
    result = client.transcribe(file_path, language)
    return result["text"]
