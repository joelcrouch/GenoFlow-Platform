#tests/test_middleware.py

import pytest
import pytest_asyncio
from fastapi import FastAPI, Response
from fastapi.middleware.gzip import GZipMiddleware
from httpx import AsyncClient, ASGITransport
import gzip
from starlette.exceptions import HTTPException as StarletteHTTPException 
from starlette.responses import PlainTextResponse
from core.middleware import ErrorHandlingMiddleware 
from typing import List

#Helper func to create a simple app for testing the middleware
def create_test_app(middleware: List=None)-> FastAPI:
    app=FastAPI()
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

    @app.get("/trigger-generic-exception")
    async def trigger_generic_exception():
        raise ValueError("Something went wrong internally")
    
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