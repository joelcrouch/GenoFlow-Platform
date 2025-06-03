- [x] Introduce core/dependencies.py and Redis:

  Add redis to requirements.txt.
  Create core/dependencies.py and move get_redis_client there.
  Add REDIS_URL to config/settings.py and .env.example.
  Update main.py's lifespan to connect to Redis.
  Run and verify the app starts without errors.

- [x] Add core/exceptions.py:

  Create core/exceptions.py and move the custom exception classes.
  Ensure main.py imports them if needed (though ErrorHandlingMiddleware will primarily use them).

- [x] Add models/user.py and models/responses.py:

  Create these files and populate them with their respective Pydantic models.

Implement core/auth.py and api/routes/auth.py:

    Add python-jose[cryptography] and passlib[bcrypt] to requirements.txt.
    Create core/auth.py and move the AuthHandler class.
    Create api/routes/auth.py and move the authentication endpoints.
    Update main.py to include_router(auth_router).
    Add JWT_SECRET to config/settings.py and .env.example.
    Test the /auth/login endpoint.

Add core/middleware.py and its components (Error Handling, Logging, Rate Limiting, Authentication):

    Add httpx and prometheus-client to requirements.txt.
    Add GZipMiddleware to main.py as it's a standard FastAPI middleware.
    Add each custom middleware (ErrorHandlingMiddleware, LoggingMiddleware, RateLimitMiddleware, AuthenticationMiddleware) to main.py's app.add_middleware in the correct order. This is crucial for their proper functioning.
    Implement setup_prometheus_metrics and the prometheus_middleware in core/monitoring.py and call setup_prometheus_metrics(app) in main.py's lifespan.
    Test with authenticated and unauthenticated requests, observe logs and rate limiting.

Implement core/service_registry.py:

    Create the file and move the ServiceRegistry class.
    Update config/settings.py with all the service URLs.
    Update main.py's lifespan to initialize the ServiceRegistry.
    Ensure get_service_registry dependency is correctly defined in core/dependencies.py.

Add Service-Specific Routes (api/routes/ingestion.py, qc.py, etc.):

    For each microservice, create its corresponding router file in api/routes/.
    Copy the relevant endpoints into each router.
    Update main.py to include_router for each new router.
    Remember to add httpx to requirements.txt as it's used for inter-service communication.

- [] TESTING!TESTING!TESTING!TESTING!TESTING!TESTING!TESTING!TESTING!
  coverage total: 59% (6/2/25)
