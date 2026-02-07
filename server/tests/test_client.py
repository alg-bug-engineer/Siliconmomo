import pytest
from client import TranscriptionClient

def test_client_initialization():
    """Test client can be initialized"""
    client = TranscriptionClient(base_url="http://localhost:8000")
    assert client.base_url == "http://localhost:8000"

@pytest.mark.asyncio
async def test_health_check():
    """Test client can check health"""
    client = TranscriptionClient()
    health = await client.health_check()
    assert "status" in health

# Integration tests would go here
# They require a running server
