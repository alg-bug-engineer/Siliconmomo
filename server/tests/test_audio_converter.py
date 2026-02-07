import pytest
from pathlib import Path
import wave
from utils.audio_converter import AudioConverter

@pytest.mark.skipif(
    not Path("test_data/sample.mp3").exists(),
    reason="Test audio file not available"
)
def test_convert_mp3_to_wav(tmp_path):
    """Test converting MP3 to 16kHz WAV"""
    converter = AudioConverter()

    input_file = Path("test_data/sample.mp3")
    output_file = tmp_path / "output.wav"

    converter.convert_to_wav(str(input_file), str(output_file))

    # Verify output is valid WAV with correct parameters
    assert output_file.exists()
    with wave.open(str(output_file), 'rb') as wf:
        assert wf.getframerate() == 16000  # 16kHz
        assert wf.getnchannels() == 1      # mono
        assert wf.getsampwidth() == 2      # 16-bit

@pytest.mark.skipif(
    not Path("test_data/sample.mp4").exists(),
    reason="Test video file not available"
)
def test_convert_video_to_wav(tmp_path):
    """Test extracting audio from video file"""
    converter = AudioConverter()

    input_file = Path("test_data/sample.mp4")
    output_file = tmp_path / "output.wav"

    converter.convert_to_wav(str(input_file), str(output_file))

    assert output_file.exists()

def test_invalid_file_raises_error():
    """Test that invalid file raises appropriate error"""
    converter = AudioConverter()

    with pytest.raises(Exception):
        converter.convert_to_wav("nonexistent.mp3", "output.wav")
