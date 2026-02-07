import pytest
from pathlib import Path
import time
from utils.file_manager import TempFileManager

def test_temp_file_context_manager():
    """Test that temp file is created and cleaned up"""
    manager = TempFileManager()

    with manager.create_temp_file(suffix=".wav") as temp_path:
        # File should exist during context
        assert Path(temp_path).parent.exists()

        # Write something to verify it's usable
        Path(temp_path).write_text("test")
        assert Path(temp_path).exists()

    # File should be deleted after context
    assert not Path(temp_path).exists()

def test_cleanup_expired_files():
    """Test cleaning up files older than threshold"""
    manager = TempFileManager()

    # Create a temp file
    old_file = manager.temp_dir / "old_file.wav"
    old_file.write_text("old")

    # Modify its timestamp to be old
    old_time = time.time() - (2 * 3600)  # 2 hours ago
    import os
    os.utime(old_file, (old_time, old_time))

    # Clean up files older than 1 hour
    manager.cleanup_expired_files(max_age_hours=1)

    # Old file should be deleted
    assert not old_file.exists()

def test_get_unique_filename():
    """Test generating unique filenames"""
    manager = TempFileManager()

    name1 = manager.get_unique_filename(suffix=".wav")
    name2 = manager.get_unique_filename(suffix=".wav")

    assert name1 != name2
    assert name1.endswith(".wav")
    assert name2.endswith(".wav")
