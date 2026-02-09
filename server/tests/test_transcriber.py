import pytest
from pathlib import Path
from transcriber import WhisperTranscriber

def test_transcriber_initialization():
    """Test transcriber validates paths on init"""
    # Should raise if whisper.cpp doesn't exist
    with pytest.raises(FileNotFoundError):
        WhisperTranscriber(
            whisper_cpp_path="/nonexistent/whisper-cli",
            model_path="/nonexistent/model.bin"
        )

@pytest.mark.skipif(
    not Path("whisper.cpp/build/bin/whisper-cli").exists(),
    reason="whisper.cpp not installed"
)
def test_transcribe_audio():
    """Test actual transcription (requires whisper.cpp setup)"""
    from config import WHISPER_CPP_PATH, MODEL_PATH

    transcriber = WhisperTranscriber(
        whisper_cpp_path=WHISPER_CPP_PATH,
        model_path=MODEL_PATH
    )

    # This requires a real audio file
    test_audio = Path("test_data/sample.wav")
    if not test_audio.exists():
        pytest.skip("Test audio not available")

    result = transcriber.transcribe(str(test_audio), language="zh")

    assert "text" in result
    assert "language" in result
    assert isinstance(result["text"], str)
    assert len(result["text"]) > 0
