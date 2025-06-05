# import pytest
# from httpx import AsyncClient

# @pytest.mark.asyncio
# async def test_read_root(client: AsyncClient):
#     """
#     Test the root endpoint ('/')
#     """
#     response=await client.get("/")
#     assert response.status_code++200
#     assert response.json()=={
#         "message": "GenoFlow API Gateway",
#         "version": "1.0.0",
#         "docs": "/docs"
#     }
    
# @pytest.mark.asyncio
# async def test_health_check(client: AsyncClient):
#     """
#     Tests the health check endpoint (`/health`).
#     """
#     response=await client.get("/health")
#     assert response.status_code==200
#     data = response.json()
#     assert data["status"] == "healthy"
#     assert "timestamp" in data
#     assert data["version"] == "1.0.0"


# tests/test_routes.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport # Import ASGITransport
import asyncio # Add this if not already present

# from main import app as fastapi_app
from core.auth import AuthHandler, get_auth_handler
from config.settings import get_settings
from core.exceptions import UnauthorizedException
from unittest.mock import patch 
import datetime
from jose import jwt 
from typing import cast
from freezegun import freeze_time
# # Update the client fixture to use ASGITransport as per httpx deprecation warning
# @pytest_asyncio.fixture(scope="session")
# async def client():
#     # Use ASGITransport to address the DeprecationWarning
#     async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
#         yield ac

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

# --- New: Fixture for AuthHandler (optional, can also call get_auth_handler directly) ---
@pytest.fixture(scope="session")
def auth_handler_instance() -> AuthHandler:
    settings = get_settings()
    return AuthHandler(secret_key=settings.jwt_secret_key)

# --- Existing tests (from previous steps) ---
@pytest.mark.asyncio
async def test_read_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "GenoFlow API Gateway",
        "version": "1.0.0",
        "docs": "/docs"
    }

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "timestamp" in response.json()
    assert response.json()["version"] == "1.0.0"

# --- New: Authentication Tests ---

@pytest.mark.asyncio
async def test_login_admin_success(client: AsyncClient):
    response = await client.post(
        "/auth/login",
        json={"username": "admin", "password": "password"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_testuser_success(client: AsyncClient):
    response = await client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    response = await client.post(
        "/auth/login",
        json={"username": "wronguser", "password": "wrongpassword"}
    )
    assert response.status_code == 401 # Unauthorized
    assert response.json()["detail"] == "Invalid credentials"

@pytest.mark.asyncio
async def test_access_protected_admin_with_admin_token(client: AsyncClient):
    # First, get admin token
    login_response = await client.post(
        "/auth/login",
        json={"username": "admin", "password": "password"}
    )
    assert login_response.status_code == 200
    admin_token = login_response.json()["access_token"]

    # Use admin token to access protected admin endpoint
    response = await client.get(
        "/auth/protected-admin",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "You have access to admin-only content!"

@pytest.mark.asyncio
async def test_access_protected_admin_with_user_token_fails(client: AsyncClient):
    # First, get testuser token
    login_response = await client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpassword"}
    )
    assert login_response.status_code == 200
    user_token = login_response.json()["access_token"]

    # Use testuser token to access protected admin endpoint (should fail)
    response = await client.get(
        "/auth/protected-admin",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 401 # Unauthorized due to insufficient permissions
    assert response.json()["detail"] == "Insufficient permissions"

@pytest.mark.asyncio
async def test_access_protected_admin_without_token_fails(client: AsyncClient):
    response = await client.get("/auth/protected-admin")
    assert response.status_code == 403 # Unauthorized (missing token)
    assert response.json()["detail"] == "Not authenticated" # This is FastAPI's default for missing HTTPBearer

@pytest.mark.asyncio
async def test_access_protected_user_with_admin_token(client: AsyncClient):
    # First, get admin token
    login_response = await client.post(
        "/auth/login",
        json={"username": "admin", "password": "password"}
    )
    assert login_response.status_code == 200
    admin_token = login_response.json()["access_token"]

    # Use admin token to access protected user endpoint
    response = await client.get(
        "/auth/protected-user",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "You have access to user content!"

@pytest.mark.asyncio
async def test_access_protected_user_with_user_token(client: AsyncClient):
    # First, get testuser token
    login_response = await client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpassword"}
    )
    assert login_response.status_code == 200
    user_token = login_response.json()["access_token"]

    # Use testuser token to access protected user endpoint
    response = await client.get(
        "/auth/protected-user",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "You have access to user content!"

@pytest.mark.asyncio
async def test_access_protected_user_without_token_fails(client: AsyncClient):
    response = await client.get("/auth/protected-user")
    assert response.status_code == 403 # Unauthorized (missing token)
    assert response.json()["detail"] == "Not authenticated"

# --- New: Unit Tests for AuthHandler (optional, but good for coverage) ---
def test_auth_handler_password_hashing(auth_handler_instance: AuthHandler):
    password = "mysecretpassword"
    hashed_password = auth_handler_instance.get_password_hash(password)
    assert auth_handler_instance.verify_password(password, hashed_password)
    assert not auth_handler_instance.verify_password("wrongpassword", hashed_password)

def test_auth_handler_token_encoding_decoding(auth_handler_instance: AuthHandler):
    user_id = "testuser123"
    roles = ["user", "viewer"]
    token = auth_handler_instance.encode_token(user_id=user_id, roles=roles, expiration_minutes=1)

    # Decode immediately
    payload = auth_handler_instance.decode_token(token)
    assert payload["sub"] == user_id
    assert "roles" in payload
    assert "user" in payload["roles"]
    assert "viewer" in payload["roles"]
    assert "exp" in payload
    
def test_auth_handler_token_expiry_freezegun(auth_handler_instance: AuthHandler):
    user_id = "expireduser"
    roles = ["user"]

    # 1. Freeze time to a specific point for token encoding
    # Use explicit UTC timezone for robustness, freezegun handles the patching
    with freeze_time("2025-01-01 12:00:00+00:00"):
        token = auth_handler_instance.encode_token(
            user_id=user_id,
            roles=roles,
            expiration_minutes=1 # Token expires 1 minute from 12:00:00 UTC
        )

    # 2. Advance time beyond token expiration (2 minutes later)
    with freeze_time("2025-01-01 12:02:00+00:00"):
        # 3. Try to decode the token; it should now be expired
        with pytest.raises(UnauthorizedException) as excinfo:
            auth_handler_instance.decode_token(token)
        assert "Invalid or expired token" in excinfo.value.detail
        assert "Signature has expired" in excinfo.value.detail   

# # Updated token expiry test using mocking
# def test_auth_handler_token_expiry_mocked(auth_handler_instance: AuthHandler):
#     user_id = "expireduser"
#     roles = ["user"]

#     # 1. Mock datetime.datetime.utcnow() for python-jose's internal use
#     # We patch the datetime module *as it's used by the jwt library*
#     # This is often 'jose.jwt.datetime'
#     # Or 'jose.jws.datetime' or 'jose.jwe.datetime' depending on exact internal path
#     # Let's try 'jose.jwt.datetime' first, as jwt.encode/decode are the main entry points
#     with patch('jose.jwt.datetime') as mock_datetime:
#         now = datetime.datetime.utcnow() # Get real utcnow for our base
#         mock_datetime.utcnow.return_value = now
#         mock_datetime.timedelta = datetime.timedelta # Ensure timedelta still works

#         # When token is encoded, it will use 'now' as its creation time
#         token = auth_handler_instance.encode_token(
#             user_id=user_id,
#             roles=roles,
#             expiration_minutes=1 # Token expires 1 minute from 'now'
#         )

#         # 2. Advance time beyond token expiration
#         mock_datetime.utcnow.return_value = now + datetime.timedelta(minutes=2) # 2 minutes later

#         # 3. Try to decode the token; it should now be expired
#         with pytest.raises(UnauthorizedException) as excinfo:
#             auth_handler_instance.decode_token(token)

#         assert "Invalid or expired token" in str(excinfo.value)

# # Updated token expiry test using mocking
# def test_auth_handler_token_expiry_mocked(auth_handler_instance: AuthHandler):
#     user_id = "expireduser"
#     roles = ["user"]

#     # 1. Mock datetime.utcnow() to a specific point in time
#     now = datetime.datetime.utcnow()
#     with patch('datetime.datetime') as mock_datetime:
#         mock_datetime.utcnow.return_value = now
#         # When token is encoded, it will use 'now' as its creation time
#         token = auth_handler_instance.encode_token(
#             user_id=user_id,
#             roles=roles,
#             expiration_minutes=1 # Token expires 1 minute from 'now'
#         )

#         # 2. Advance time beyond token expiration
#         mock_datetime.utcnow.return_value = now + datetime.timedelta(minutes=2) # 2 minutes later

#         # 3. Try to decode the token; it should now be expired
#         with pytest.raises(UnauthorizedException) as excinfo:
#             auth_handler_instance.decode_token(token)

#         assert "Invalid or expired token" in str(excinfo.value)

# def test_auth_handler_token_expiry(auth_handler_instance: AuthHandler):
#     user_id = "expireduser"
#     roles = ["user"]
#     # Create a token that expires very quickly
#     # Use a slightly longer sleep to ensure expiration across different system loads
#     token = auth_handler_instance.encode_token(user_id=user_id, roles=roles, expiration_minutes=0.001)

#     import time
#     time.sleep(0.02) # Give it a bit more time to ensure it expires, e.g., 20ms

#     # Change the expected exception type to UnauthorizedException
#     with pytest.raises(UnauthorizedException) as excinfo:
#         auth_handler_instance.decode_token(token)
#     assert "Invalid or expired token" in str(excinfo.value)
#     # You can also assert on the HTTPException status code if UnauthorizedException includes it
#     # assert excinfo.value.status_code == 401 # 
# # def test_auth_handler_token_expiry(auth_handler_instance: AuthHandler):
# #     user_id = "expireduser"
# #     roles = ["user"]
# #     # Create a token that expires very quickly
# #     token = auth_handler_instance.encode_token(user_id=user_id, roles=roles, expiration_minutes=0.001) # Very short expiry

# #     # Wait for the token to expire
# #     # This sleep makes the test slow, but demonstrates expiry
# #     # In real world, you might mock datetime for faster tests
# #     import time
# #     time.sleep(0.01) # Wait longer than 0.001 minutes

# #     with pytest.raises(UnauthorizedException) as excinfo: # Catching generic Exception as UnauthorizedException is not directly exposed without app context
# #         auth_handler_instance.decode_token(token)
# #     assert "Invalid or expired token" in str(excinfo.value) # Check for the detail in the exception message