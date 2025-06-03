import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_read_root(client: AsyncClient):
    """
    Test the root endpoint ('/')
    """
    response=await client.get("/")
    assert response.status_code++200
    assert response.json()=={
        "message": "GenoFlow API Gateway",
        "version": "1.0.0",
        "docs": "/docs"
    }
    
@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """
    Tests the health check endpoint (`/health`).
    """
    response=await client.get("/health")
    assert response.status_code==200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == "1.0.0"