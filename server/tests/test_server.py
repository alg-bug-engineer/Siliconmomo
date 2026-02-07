import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import io

# We'll import app after creating server.py
# from server import app

@pytest.fixture
def client():
    from server import app
    return TestClient(app)

def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "whisper_ready" in data

def test_info_endpoint(client):
    """Test info endpoint"""
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert "model" in data

@pytest.mark.skipif(
    not Path("test_data/sample.wav").exists(),
    reason="Test audio not available"
)
def test_transcribe_endpoint(client):
    """Test transcription endpoint"""
    with open("test_data/sample.wav", "rb") as f:
        response = client.post(
            "/transcribe",
            files={"file": ("test.wav", f, "audio/wav")}
        )

    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "language" in data
    assert "processing_time" in data

def test_transcribe_file_too_large(client):
    """Test file size limit"""
    # Create a fake large file
    large_file = io.BytesIO(b"0" * (101 * 1024 * 1024))  # 101 MB

    response = client.post(
        "/transcribe",
        files={"file": ("large.wav", large_file, "audio/wav")}
    )

    assert response.status_code == 413  # Payload too large
