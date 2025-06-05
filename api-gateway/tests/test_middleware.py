#tests/test_middleware.py
import datetime
import pytest
import pytest_asyncio
from fastapi import FastAPI, Response,status
from fastapi.middleware.gzip import GZipMiddleware
from httpx import AsyncClient, ASGITransport
import gzip
import logging
from starlette.exceptions import HTTPException as StarletteHTTPException 
from starlette.responses import PlainTextResponse, JSONResponse
from core.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    # REQUEST_COUNTS,          # <-- ADD THIS IMPORT
    # RATE_LIMIT_MAX_REQUESTS, # <-- ADD THIS IMPORT
    # RATE_LIMIT_DURATION_SECONDS # <-- ADD THIS IMPORT
)
from typing import List
import time
from freezegun import freeze_time

# Define constants for testing locally since they are no longer module globals
TEST_RATE_LIMIT_MAX_REQUESTS = 10
TEST_RATE_LIMIT_DURATION_SECONDS = 60

#Helper func to create a simple app for testing the middleware
def create_test_app(middleware: List = None) -> FastAPI:
    app = FastAPI()
    
    # The REQUEST_COUNTS.clear() logic is no longer needed here because
    # each new RateLimitMiddleware instance will have its own clean state.
    # if middleware and any(mw_class == RateLimitMiddleware for mw_class, _ in middleware):
    #     REQUEST_COUNTS.clear() # REMOVE THIS LINE

    if middleware:
        for mw_class, mw_kwargs in middleware:
            app.add_middleware(mw_class, **mw_kwargs)
            
    @app.get("/large-data")
    async def get_large_date():
        # Return PlainTextResponse to ensure no JSON serialization interferes with GZip
        return PlainTextResponse("a" * 2000) 
    
    @app.get("/small-data")
    async def get_small_data():
        # Return PlainTextResponse for consistent plain text comparison
        return PlainTextResponse("small")
    
    # @app.get("/error-test")
    # async def get_error_test():
    #     raise HTTPExceptions(status_code=400, detail="Test error")# for err handling middleware
    @app.get("/trigger-http-exception")
    async def trigger_http_exception():
        raise StarletteHTTPException(status_code=400, detail="Custom HTTP Error")

    @app.get("/trigger-validation-error")
    async def trigger_validation_error(item_id: int):
        # This will trigger a 422 Unprocessable Entity if item_id is not an int
        # FastAPI's internal validation will raise a StarletteHTTPException
        return {"item_id": item_id}

    @app.get("/trigger-internal-server-error")
    async def trigger_internal_server_error():
        # Simulate an unexpected internal error
        raise ValueError("Something went wrong internally during processing")
    
    @app.get("/trigger-generic-exception")
    async def trigger_generic_exception():
        raise ValueError("Something went wrong internally")
    
    @app.get("/rate-limited-endpoint") # <-- NEW ENDPOINT for rate limit tests
    async def rate_limited_endpoint():
        return {"message": "Access granted"}
    
    return app

#fixture for a client to test specific midware
@pytest_asyncio.fixture(scope="function")
async def middleware_test_client():
    #this fixture will be created for each test function
    yield
    
# Test for GZipMiddleware
@pytest.mark.asyncio
async def test_gzip_middleware_compresses_large_response():
    # Create an app with ONLY GZipMiddleware for this test
    app = create_test_app(middleware=[(GZipMiddleware, {"minimum_size": 1000})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/large-data")
        assert response.status_code == 200
        assert "content-encoding" in response.headers
        assert response.headers["content-encoding"] == "gzip"
        # Verify content is actually gzipped and can be decompressed
        #assert gzip.decompress(response.content).decode('utf-8') == "a" * 2000 # <-- Added .decode('utf-8')
         # Verify content is already decompressed by httpx and matches
        assert response.content.decode('utf-8') == "a" * 2000 # <--- FIX: Removed gzip.decompress()


@pytest.mark.asyncio
async def test_gzip_middleware_does_not_compress_small_response():
    app = create_test_app(middleware=[(GZipMiddleware, {"minimum_size": 1000})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/small-data")
        assert response.status_code == 200
        assert "content-encoding" not in response.headers # Should not be gzipped
        assert response.text == "small"
     
@pytest.mark.asyncio
async def test_gzip_middleware_compresses_at_boundary():
    # Response of exactly 1000 bytes
    app = create_test_app(middleware=[(GZipMiddleware, {"minimum_size": 1000})])
    @app.get("/exact-size")
    async def get_exact_size():
        return PlainTextResponse("b" * 1000) # Exactly 1000 bytes
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/exact-size")
        assert response.status_code == 200
        assert "content-encoding" in response.headers
        assert response.headers["content-encoding"] == "gzip"
        assert response.content.decode('utf-8') == "b" * 1000
  
@pytest.mark.asyncio
async def test_gzip_middleware_does_not_compress_below_boundary():
    # Response of 999 bytes
    app = create_test_app(middleware=[(GZipMiddleware, {"minimum_size": 1000})])
    @app.get("/below-size")
    async def get_below_size():
        return PlainTextResponse("c" * 999) # 999 bytes
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/below-size")
        assert response.status_code == 200
        assert "content-encoding" not in response.headers # Should NOT be gzipped
        assert response.text == "c" * 999  
         
# Test for ErrorHandlingMiddleware
@pytest.mark.asyncio
async def test_error_handling_middleware_catches_http_exception():
    app = create_test_app(middleware=[(ErrorHandlingMiddleware, {})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/trigger-http-exception")
        assert response.status_code == 400
        assert response.json() == {"detail": "Custom HTTP Error"}

@pytest.mark.asyncio
async def test_error_handling_middleware_catches_generic_exception():
    app = create_test_app(middleware=[(ErrorHandlingMiddleware, {})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/trigger-generic-exception")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal Server Error"}
        
@pytest.mark.asyncio
async def test_error_handling_middleware_catches_validation_error():
    app = create_test_app(middleware=[(ErrorHandlingMiddleware, {})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Pass a non-integer to item_id to trigger a validation error
        response = await client.get("/trigger-validation-error?item_id=not_an_int")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # 422
        # FastAPI's validation error detail can be complex, check for presence of expected message
        
               
        assert "detail" in response.json()
        assert any(err["type"] == "int_parsing" for err in response.json()["detail"])
        assert response.headers["content-type"] == "application/json"
        
@pytest.mark.asyncio
async def test_error_handling_middleware_catches_internal_server_error():
    app = create_test_app(middleware=[(ErrorHandlingMiddleware, {})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/trigger-internal-server-error") # Updated endpoint name
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal Server Error"}
        assert response.headers["content-type"] == "application/json"
         
@pytest.mark.asyncio
async def test_error_handling_middleware_catches_validation_error():
    app = create_test_app(middleware=[(ErrorHandlingMiddleware, {})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Pass a non-integer to item_id to trigger a validation error
        response = await client.get("/trigger-validation-error?item_id=not_an_int")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # 422
        # FastAPI's validation error detail can be complex, check for presence of expected message
        assert "detail" in response.json()
        assert any(err["type"] == "int_parsing" for err in response.json()["detail"])
        assert response.headers["content-type"] == "application/json"

# NEW: Test an endpoint that doesn't exist (FastAPI's default 404 behavior, but ensures it's JSON)
@pytest.mark.asyncio
async def test_error_handling_middleware_handles_404_not_found():
    app = create_test_app(middleware=[(ErrorHandlingMiddleware, {})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/non-existent-path")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "Not Found"} # Default FastAPI 404 JSON response
        assert response.headers["content-type"] == "application/json"
         
@pytest.mark.asyncio
async def test_logging_middleware(caplog):
    app = create_test_app(middleware=[(LoggingMiddleware, {})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with caplog.at_level(logging.INFO): # Capture INFO level logs
            response = await client.get("/small-data")
            assert response.status_code == 200

        # Check if logs contain the expected messages
        assert any("Incoming Request: GET /small-data from 127.0.0.1" in record.message for record in caplog.records)
        assert any("Outgoing Response: 200 GET /small-data" in record.message for record in caplog.records)

        # assert any("Incoming Request: GET /small-data from testclient" in record.message for record in caplog.records)
        # assert any("Outgoing Response: 200 GET /small-data" in record.message for record in caplog.records)
        
# Test that requests within the limit succeed, and requests beyond the limit fail
# --- RateLimitMiddleware Tests (using local constants) ---

@pytest.mark.asyncio
async def test_rate_limit_middleware_exceeds_limit():
    app = create_test_app(middleware=[(RateLimitMiddleware, {})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Send requests up to the limit
        for i in range(TEST_RATE_LIMIT_MAX_REQUESTS): # <-- Use local constant
            response = await client.get("/rate-limited-endpoint")
            assert response.status_code == status.HTTP_200_OK, f"Request {i+1} failed unexpectedly"
            assert response.json() == {"message": "Access granted"}

        # Send one more request - this should be rate-limited
        response = await client.get("/rate-limited-endpoint")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.json() == {"detail": "Too many requests. Please try again later."}

@pytest.mark.asyncio
@freeze_time("2024-01-01 10:00:00") # Start time for test
async def test_rate_limit_middleware_resets_after_duration():
    app = create_test_app(middleware=[(RateLimitMiddleware, {})])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exhaust the limit
        for _ in range(TEST_RATE_LIMIT_MAX_REQUESTS):
            await client.get("/rate-limited-endpoint")

        # The next request should be blocked
        response = await client.get("/rate-limited-endpoint")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # Advance time just past the duration
        initial_time = datetime.datetime(2024, 1, 1, 10, 0, 0)
        future_time = initial_time + datetime.timedelta(seconds=TEST_RATE_LIMIT_DURATION_SECONDS + 1)

        with freeze_time(future_time): # Pass the datetime object directly
            # Now, a new request should succeed because the limit has reset
            response = await client.get("/rate-limited-endpoint")
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {"message": "Access granted"}

        # Verify that sending another request immediately after reset still works (count is 1)
        response = await client.get("/rate-limited-endpoint")
        assert response.status_code == status.HTTP_200_OK