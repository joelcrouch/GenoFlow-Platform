# tests/conftest.py

# tests/conftest.py

import pytest
import pytest_asyncio # ADD THIS IMPORT
from httpx import AsyncClient
from main import app as fastapi_app # Import your FastAPI app instance

# Change @pytest.fixture to @pytest_asyncio.fixture
@pytest_asyncio.fixture(scope="session") # CHANGE THIS LINE
async def client():
    """
    Creates an asynchronous test client for the FastAPI application.
    This client can make requests to your app without actually running a Uvicorn server.
    """
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(scope="session") # Keep this as pytest.fixture, as it's not an async fixture
def anyio_backend():
    """
    Fixture required by pytest-asyncio to specify the AnyIO backend.
    """
    return "asyncio"