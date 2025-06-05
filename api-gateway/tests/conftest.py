# tests/conftest.py

import pytest
import pytest_asyncio
from httpx import AsyncClient
#from main import app as fastapi_app # Import your FastAPI app instance
from core.auth import AuthHandler
import datetime
from freezegun import freeze_time
from unittest.mock import patch
#from core.middleware import REQUEST_COUNTS
from main import create_application

# Change @pytest.fixture to @pytest_asyncio.fixture
@pytest_asyncio.fixture(scope="function") 
async def client():
    # --- CRITICAL CHANGE HERE ---
    # Create a fresh application instance for EACH test function.
    # This guarantees that all middleware (including RateLimitMiddleware)
    # and their internal states are completely re-initialized for every test.
    fresh_app = create_application()

    # The manual REQUEST_COUNTS.clear() is no longer needed here
    # because 'fresh_app' contains a new, clean RateLimitMiddleware instance.
    # REQUEST_COUNTS.clear() # <-- REMOVE THIS LINE

    async with AsyncClient(app=fresh_app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def auth_handler_fixture():
    return AuthHandler()

@pytest.fixture(scope="session") # Keep this as pytest.fixture, as it's not an async fixture
def anyio_backend():
    """
    Fixture required by pytest-asyncio to specify the AnyIO backend.
    """
    return "asyncio"