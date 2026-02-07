import uuid
import logging
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timedelta
import time
from config import TEMP_DIR, TEMP_FILE_EXPIRE_HOURS

logger = logging.getLogger(__name__)

class TempFileManager:
    """Manage temporary files with automatic cleanup"""

    def __init__(self, temp_dir: Path = TEMP_DIR):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True, parents=True)

    def get_unique_filename(self, suffix: str = "") -> str:
        """
        Generate a unique filename using UUID.

        Args:
            suffix: File extension (e.g., ".wav")

        Returns:
            Unique filename string
        """
        unique_id = uuid.uuid4().hex
        return f"{unique_id}{suffix}"

    @contextmanager
    def create_temp_file(self, suffix: str = ""):
        """
        Context manager that creates a temp file and cleans it up.

        Args:
            suffix: File extension

        Yields:
            Path to temporary file
        """
        filename = self.get_unique_filename(suffix)
        filepath = self.temp_dir / filename

        try:
            logger.debug(f"Created temp file: {filepath}")
            yield str(filepath)
        finally:
            # Clean up the file
            if filepath.exists():
                filepath.unlink()
                logger.debug(f"Deleted temp file: {filepath}")

    def cleanup_expired_files(self, max_age_hours: int = TEMP_FILE_EXPIRE_HOURS):
        """
        Delete files older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before deletion
        """
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        deleted_count = 0

        for filepath in self.temp_dir.iterdir():
            if not filepath.is_file():
                continue

            # Check file age
            file_age = now - filepath.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    filepath.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted expired temp file: {filepath}")
                except Exception as e:
                    logger.error(f"Failed to delete {filepath}: {e}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired temp files")

    def get_temp_path(self, suffix: str = "") -> Path:
        """
        Get path for a new temp file without context manager.
        Caller is responsible for cleanup.

        Args:
            suffix: File extension

        Returns:
            Path object for temp file
        """
        filename = self.get_unique_filename(suffix)
        return self.temp_dir / filename
