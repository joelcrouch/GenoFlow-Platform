# main.py - FastAPI Application Entry Point
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import logging
import time
import uuid
from typing import Dict, Any

# Internal imports
from config.settings import get_settings
from core.dependencies import get_redis_client, get_service_registry
from core.middleware import (
    AuthenticationMiddleware,
    RateLimitMiddleware,
    LoggingMiddleware,
    ErrorHandlingMiddleware
)
from api.routes import (
    auth_router,
    ingestion_router,
    qc_router,
    pipeline_router,
    execution_router,
    results_router,
    monitoring_router
)
from core.exceptions import GenoFlowException
from core.auth import AuthHandler
from core.service_registry import ServiceRegistry
from core.monitoring import setup_prometheus_metrics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting GenoFlow API Gateway...")
    
    # Initialize Redis connection
    redis_client = await get_redis_client()
    app.state.redis = redis_client
    
    # Initialize service registry
    service_registry = ServiceRegistry(redis_client)
    await service_registry.initialize()
    app.state.service_registry = service_registry
    
    # Setup monitoring
    setup_prometheus_metrics(app)
    
    logger.info("GenoFlow API Gateway started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down GenoFlow API Gateway...")
    if hasattr(app.state, 'redis'):
        await app.state.redis.close()
    logger.info("GenoFlow API Gateway shutdown complete")

# Create FastAPI application
def create_application() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="GenoFlow API Gateway",
        description="Clinical Sequencing Pipeline API Gateway",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Add middleware (order matters!)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Custom middleware
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthenticationMiddleware)
    
    # Include routers
    app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
    app.include_router(ingestion_router, prefix="/api/v1/ingestion", tags=["Data Ingestion"])
    app.include_router(qc_router, prefix="/api/v1/qc", tags=["Quality Control"])
    app.include_router(pipeline_router, prefix="/api/v1/pipelines", tags=["Pipeline Management"])
    app.include_router(execution_router, prefix="/api/v1/execution", tags=["Workflow Execution"])
    app.include_router(results_router, prefix="/api/v1/results", tags=["Results Management"])
    app.include_router(monitoring_router, prefix="/api/v1/monitoring", tags=["Monitoring"])
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "1.0.0"
        }
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "GenoFlow API Gateway",
            "version": "1.0.0",
            "docs": "/docs"
        }
    
    return app

# Create the app instance
app = create_application()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )

# =============================================================================
# config/settings.py - Configuration Management
# =============================================================================

from pydantic import BaseSettings, Field
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Application settings
    app_name: str = "GenoFlow API Gateway"
    version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Security
    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    refresh_token_expiry_days: int = 30
    
    # CORS
    allowed_origins: List[str] = ["http://localhost:3000", "https://genoflow.com"]
    
    # Redis configuration
    redis_url: str = Field("redis://localhost:6379", env="REDIS_URL")
    redis_db: int = 0
    redis_max_connections: int = 20
    
    # Rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 200
    
    # Service URLs
    data_ingestion_service_url: str = Field(..., env="DATA_INGESTION_SERVICE_URL")
    qc_service_url: str = Field(..., env="QC_SERVICE_URL")
    pipeline_service_url: str = Field(..., env="PIPELINE_SERVICE_URL")
    execution_service_url: str = Field(..., env="EXECUTION_SERVICE_URL")
    results_service_url: str = Field(..., env="RESULTS_SERVICE_URL")
    monitoring_service_url: str = Field(..., env="MONITORING_SERVICE_URL")
    auth_service_url: str = Field(..., env="AUTH_SERVICE_URL")
    
    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Singleton pattern for settings
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# =============================================================================
# core/dependencies.py - Dependency Injection
# =============================================================================

import redis.asyncio as redis
from fastapi import Depends, HTTPException, status
from typing import Optional
import httpx

from config.settings import get_settings
from core.auth import AuthHandler
from core.service_registry import ServiceRegistry
from models.user import User

# Redis client singleton
_redis_client: Optional[redis.Redis] = None

async def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url,
            db=settings.redis_db,
            max_connections=settings.redis_max_connections,
            decode_responses=True
        )
    return _redis_client

# HTTP client for service communication
async def get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30.0)

# Auth handler dependency
async def get_auth_handler(
    redis_client: redis.Redis = Depends(get_redis_client)
) -> AuthHandler:
    settings = get_settings()
    return AuthHandler(redis_client, settings.jwt_secret, settings.jwt_algorithm)

# Service registry dependency
async def get_service_registry(
    redis_client: redis.Redis = Depends(get_redis_client)
) -> ServiceRegistry:
    return ServiceRegistry(redis_client)

# Current user dependency
async def get_current_user(
    auth_handler: AuthHandler = Depends(get_auth_handler)
) -> User:
    # This will be populated by the AuthenticationMiddleware
    # The middleware will extract and validate the JWT token
    user = getattr(get_current_user, 'current_user', None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

# Optional current user (for public endpoints that benefit from user context)
async def get_current_user_optional(
    auth_handler: AuthHandler = Depends(get_auth_handler)
) -> Optional[User]:
    return getattr(get_current_user_optional, 'current_user', None)

# =============================================================================
# core/auth.py - Authentication Handler
# =============================================================================

import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import redis.asyncio as redis
import json
import uuid

from models.user import User, TokenPair
from core.exceptions import AuthenticationError

class AuthHandler:
    def __init__(self, redis_client: redis.Redis, jwt_secret: str, algorithm: str = "HS256"):
        self.redis = redis_client
        self.jwt_secret = jwt_secret
        self.algorithm = algorithm
    
    async def create_access_token(self, user: User) -> str:
        """Create JWT access token"""
        now = datetime.utcnow()
        expire = now + timedelta(minutes=60)  # 1 hour
        
        payload = {
            "sub": user.user_id,
            "username": user.username,
            "roles": user.roles,
            "iat": now.timestamp(),
            "exp": expire.timestamp(),
            "type": "access"
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.algorithm)
    
    async def create_refresh_token(self, user: User) -> str:
        """Create refresh token"""
        now = datetime.utcnow()
        expire = now + timedelta(days=30)  # 30 days
        
        token_id = str(uuid.uuid4())
        payload = {
            "sub": user.user_id,
            "token_id": token_id,
            "iat": now.timestamp(),
            "exp": expire.timestamp(),
            "type": "refresh"
        }
        
        refresh_token = jwt.encode(payload, self.jwt_secret, algorithm=self.algorithm)
        
        # Store refresh token in Redis
        await self.redis.setex(
            f"refresh_token:{token_id}",
            timedelta(days=30),
            json.dumps({"user_id": user.user_id, "created_at": now.isoformat()})
        )
        
        return refresh_token
    
    async def verify_token(self, token: str) -> User:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.algorithm])
            
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")
            
            # Create user object from token payload
            user = User(
                user_id=payload["sub"],
                username=payload["username"],
                roles=payload["roles"]
            )
            
            return user
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.JWTError:
            raise AuthenticationError("Invalid token")
    
    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Generate new access token using refresh token"""
        try:
            payload = jwt.decode(refresh_token, self.jwt_secret, algorithms=[self.algorithm])
            
            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid refresh token")
            
            token_id = payload["token_id"]
            
            # Check if refresh token exists in Redis
            token_data = await self.redis.get(f"refresh_token:{token_id}")
            if not token_data:
                raise AuthenticationError("Refresh token not found or expired")
            
            # Get user data (in production, fetch from user service)
            user = User(
                user_id=payload["sub"],
                username="",  # Would fetch from user service
                roles=[]      # Would fetch from user service
            )
            
            # Create new tokens
            new_access_token = await self.create_access_token(user)
            new_refresh_token = await self.create_refresh_token(user)
            
            # Invalidate old refresh token
            await self.redis.delete(f"refresh_token:{token_id}")
            
            return TokenPair(
                access_token=new_access_token,
                refresh_token=new_refresh_token
            )
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Refresh token has expired")
        except jwt.JWTError:
            raise AuthenticationError("Invalid refresh token")
    
    async def revoke_token(self, user_id: str, token_id: str):
        """Revoke a specific refresh token"""
        await self.redis.delete(f"refresh_token:{token_id}")
    
    async def check_permissions(self, user: User, resource: str, action: str) -> bool:
        """Check if user has permission for specific resource and action"""
        # Simple role-based check (extend with more sophisticated RBAC)
        if "admin" in user.roles:
            return True
        
        # Define role permissions
        permissions = {
            "analyst": {
                "ingestion": ["read", "write"],
                "qc": ["read", "write"],
                "pipelines": ["read"],
                "execution": ["read", "write"],
                "results": ["read"],
                "monitoring": ["read"]
            },
            "researcher": {
                "results": ["read"],
                "monitoring": ["read"]
            }
        }
        
        for role in user.roles:
            if role in permissions:
                if resource in permissions[role]:
                    if action in permissions[role][resource]:
                        return True
        
        return False

# =============================================================================
# core/service_registry.py - Service Discovery and Load Balancing
# =============================================================================

import httpx
import json
from typing import Dict, List, Optional
import redis.asyncio as redis
import random
import time
from dataclasses import dataclass

@dataclass
class ServiceInstance:
    url: str
    health_score: float = 1.0
    last_check: float = 0.0
    failures: int = 0

class ServiceRegistry:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.services: Dict[str, List[ServiceInstance]] = {}
        self.circuit_breakers: Dict[str, Dict] = {}
    
    async def initialize(self):
        """Initialize service registry with default services"""
        from config.settings import get_settings
        settings = get_settings()
        
        # Register default services
        services = {
            "data_ingestion": [settings.data_ingestion_service_url],
            "qc": [settings.qc_service_url],
            "pipeline": [settings.pipeline_service_url],
            "execution": [settings.execution_service_url],
            "results": [settings.results_service_url],
            "monitoring": [settings.monitoring_service_url],
            "auth": [settings.auth_service_url]
        }
        
        for service_name, urls in services.items():
            await self.register_service(service_name, urls)
    
    async def register_service(self, name: str, urls: List[str]):
        """Register a service with multiple instances"""
        instances = [ServiceInstance(url=url) for url in urls]
        self.services[name] = instances
        
        # Store in Redis for persistence
        await self.redis.setex(
            f"service:{name}",
            3600,  # 1 hour TTL
            json.dumps(urls)
        )
    
    async def get_service_url(self, service_name: str) -> str:
        """Get healthy service URL with load balancing"""
        if service_name not in self.services:
            # Try to load from Redis
            urls_json = await self.redis.get(f"service:{service_name}")
            if urls_json:
                urls = json.loads(urls_json)
                await self.register_service(service_name, urls)
            else:
            raise AuthenticationError("Invalid credentials")
        
        # Generate tokens
        access_token = await auth_handler.create_access_token(user)
        refresh_token = await auth_handler.create_refresh_token(user)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,
            user=user
        )
    
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_request: RefreshRequest,
    auth_handler: AuthHandler = Depends(get_auth_handler)
):
    """Refresh access token using refresh token"""
    try:
        token_pair = await auth_handler.refresh_access_token(refresh_request.refresh_token)
        
        # Get user info (in production, fetch from user service)
        user = User(user_id="1", username="admin", roles=["admin"])
        
        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=3600,
            user=user
        )
    
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@auth_router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user and invalidate tokens"""
    # In production, invalidate all user tokens
    return {"message": "Logged out successfully"}

@auth_router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

# =============================================================================
# api/routes/ingestion.py - Data Ingestion Routes
# =============================================================================

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
import httpx
from typing import Optional

from core.dependencies import get_service_registry, get_current_user, get_http_client
from core.service_registry import ServiceRegistry
from models.user import User
from models.responses import APIResponse

ingestion_router = APIRouter()

@ingestion_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    sample_id: str = Form(...),
    project_id: str = Form(...),
    metadata: Optional[str] = Form(None),
    checksum: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Upload sequencing data file"""
    try:
        service_url = await service_registry.get_service_url("data_ingestion")
        
        # Prepare form data for backend service
        files = {"file": (file.filename, file.file, file.content_type)}
        data = {
            "sample_id": sample_id,
            "project_id": project_id,
            "user_id": current_user.user_id
        }
        
        if metadata:
            data["metadata"] = metadata
        if checksum:
            data["checksum"] = checksum
        
        # Forward request to data ingestion service
        response = await http_client.post(
            f"{service_url}/upload",
            files=files,
            data=data,
            timeout=300  # 5 minutes for large files
        )
        
        if response.status_code == 200:
            await service_registry.record_success("data_ingestion", service_url)
            return response.json()
        else:
            await service_registry.record_failure("data_ingestion", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("data_ingestion", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@ingestion_router.get("/upload/{upload_id}")
async def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Get upload status"""
    try:
        service_url = await service_registry.get_service_url("data_ingestion")
        
        response = await http_client.get(f"{service_url}/upload/{upload_id}")
        
        if response.status_code == 200:
            await service_registry.record_success("data_ingestion", service_url)
            return response.json()
        else:
            await service_registry.record_failure("data_ingestion", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("data_ingestion", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

# =============================================================================
# api/routes/qc.py - Quality Control Routes
# =============================================================================

from fastapi import APIRouter
from pydantic import BaseModel

qc_router = APIRouter()

class QCAnalysisRequest(BaseModel):
    sample_id: str
    data_path: str
    qc_profile: str = "standard"
    parameters: dict = {}

@qc_router.post("/analyze")
async def initiate_qc_analysis(
    request: QCAnalysisRequest,
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Initiate quality control analysis"""
    try:
        service_url = await service_registry.get_service_url("qc")
        
        payload = request.dict()
        payload["user_id"] = current_user.user_id
        
        response = await http_client.post(f"{service_url}/analyze", json=payload)
        
        if response.status_code == 200:
            await service_registry.record_success("qc", service_url)
            return response.json()
        else:
            await service_registry.record_failure("qc", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("qc", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@qc_router.get("/results/{qc_job_id}")
async def get_qc_results(
    qc_job_id: str,
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Get quality control results"""
    try:
        service_url = await service_registry.get_service_url("qc")
        
        response = await http_client.get(f"{service_url}/results/{qc_job_id}")
        
        if response.status_code == 200:
            await service_registry.record_success("qc", service_url)
            return response.json()
        else:
            await service_registry.record_failure("qc", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("qc", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

# =============================================================================
# api/routes/pipeline.py - Pipeline Management Routes  
# =============================================================================

from fastapi import APIRouter, Query
from typing import Optional, List

pipeline_router = APIRouter()

class PipelineConfigRequest(BaseModel):
    name: str
    parameters: dict
    resource_requirements: dict

@pipeline_router.get("/")
async def list_pipelines(
    type: Optional[str] = Query(None),
    version: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """List available pipelines"""
    try:
        service_url = await service_registry.get_service_url("pipeline")
        
        params = {}
        if type:
            params["type"] = type
        if version:
            params["version"] = version
        if status:
            params["status"] = status
        
        response = await http_client.get(f"{service_url}/pipelines", params=params)
        
        if response.status_code == 200:
            await service_registry.record_success("pipeline", service_url)
            return response.json()
        else:
            await service_registry.record_failure("pipeline", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("pipeline", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@pipeline_router.post("/{pipeline_id}/configurations")
async def create_pipeline_configuration(
    pipeline_id: str,
    config_request: PipelineConfigRequest,
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Create pipeline configuration"""
    try:
        service_url = await service_registry.get_service_url("pipeline")
        
        payload = config_request.dict()
        payload["user_id"] = current_user.user_id
        
        response = await http_client.post(
            f"{service_url}/pipelines/{pipeline_id}/configurations",
            json=payload
        )
        
        if response.status_code == 200:
            await service_registry.record_success("pipeline", service_url)
            return response.json()
        else:
            await service_registry.record_failure("pipeline", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("pipeline", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

# =============================================================================
# api/routes/execution.py - Workflow Execution Routes
# =============================================================================

execution_router = APIRouter()

class JobSubmissionRequest(BaseModel):
    pipeline_id: str
    config_id: str
    sample_ids: List[str]
    priority: str = "normal"
    notification_settings: dict = {}

@execution_router.post("/jobs")
async def submit_pipeline_job(
    job_request: JobSubmissionRequest,
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Submit pipeline job for execution"""
    try:
        service_url = await service_registry.get_service_url("execution")
        
        payload = job_request.dict()
        payload["user_id"] = current_user.user_id
        
        response = await http_client.post(f"{service_url}/jobs", json=payload)
        
        if response.status_code == 200:
            await service_registry.record_success("execution", service_url)
            return response.json()
        else:
            await service_registry.record_failure("execution", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("execution", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@execution_router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Get job execution status"""
    try:
        service_url = await service_registry.get_service_url("execution")
        
        response = await http_client.get(f"{service_url}/jobs/{job_id}")
        
        if response.status_code == 200:
            await service_registry.record_success("execution", service_url)
            return response.json()
        else:
            await service_registry.record_failure("execution", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("execution", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

# =============================================================================
# api/routes/results.py - Results Management Routes
# =============================================================================

results_router = APIRouter()

class DownloadLinksRequest(BaseModel):
    files: List[str]
    expiration_hours: int = 24

@results_router.get("/{job_id}")
async def get_analysis_results(
    job_id: str,
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Get analysis results for a job"""
    try:
        service_url = await service_registry.get_service_url("results")
        
        response = await http_client.get(f"{service_url}/{job_id}")
        
        if response.status_code == 200:
            await service_registry.record_success("results", service_url)
            return response.json()
        else:
            await service_registry.record_failure("results", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("results", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@results_router.post("/{job_id}/download-links")
async def generate_download_links(
    job_id: str,
    download_request: DownloadLinksRequest,
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Generate download links for result files"""
    try:
        service_url = await service_registry.get_service_url("results")
        
        payload = download_request.dict()
        payload["user_id"] = current_user.user_id
        
        response = await http_client.post(
            f"{service_url}/{job_id}/download-links",
            json=payload
        )
        
        if response.status_code == 200:
            await service_registry.record_success("results", service_url)
            return response.json()
        else:
            await service_registry.record_failure("results", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("results", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

# =============================================================================
# api/routes/monitoring.py - Monitoring Routes
# =============================================================================

from datetime import datetime

monitoring_router = APIRouter()

@monitoring_router.get("/metrics")
async def get_system_metrics(
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    metric_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    service_registry: ServiceRegistry = Depends(get_service_registry),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """Get system metrics"""
    try:
        service_url = await service_registry.get_service_url("monitoring")
        
        params = {}
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        if metric_type:
            params["metric_type"] = metric_type
        
        response = await http_client.get(f"{service_url}/metrics", params=params)
        
        if response.status_code == 200:
            await service_registry.record_success("monitoring", service_url)
            return response.json()
        else:
            await service_registry.record_failure("monitoring", service_url)
            raise HTTPException(status_code=response.status_code, detail=response.text)
    
    except httpx.RequestError as e:
        await service_registry.record_failure("monitoring", service_url)
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

# =============================================================================
# core/monitoring.py - Prometheus Metrics Setup
# =============================================================================

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Response
import time

# Define metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Active connections')

def setup_prometheus_metrics(app):
    """Setup Prometheus metrics endpoint"""
    
    @app.get("/metrics")
    async def get_metrics():
        """Prometheus metrics endpoint"""
        return Response(generate_latest(), media_type="text/plain")
    
    @app.middleware("http")
    async def prometheus_middleware(request, call_next):
        """Middleware to collect Prometheus metrics"""
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Record metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_DURATION.observe(time.time() - start_time)
        
        return response

# =============================================================================
# Start the application
# =============================================================================

# Create requirements.txt file
requirements_txt = """
fastapi==0.104.1
uvicorn[standard]==0.24.0
redis==5.0.1
httpx==0.25.2
pydantic==2.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
prometheus-client==0.19.0
python-multipart==0.0.6
"""

# Create .env.example file
env_example = """
# JWT Configuration
JWT_SECRET=your-super-secret-jwt-key-here

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Service URLs
DATA_INGESTION_SERVICE_URL=http://localhost:8001
QC_SERVICE_URL=http://localhost:8002
PIPELINE_SERVICE_URL=http://localhost:8003
EXECUTION_SERVICE_URL=http://localhost:8004
RESULTS_SERVICE_URL=http://localhost:8005
MONITORING_SERVICE_URL=http://localhost:8006
AUTH_SERVICE_URL=http://localhost:8007

# Application Configuration
DEBUG=true
"""

# Create docker-compose.yml for local development
docker_compose = """
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    
  api-gateway:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=dev-secret-key
    depends_on:
      - redis
    volumes:
      - .:/app
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  redis_data:
"""

# Create Dockerfile
dockerfile = """
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

# To run the application:
# 1. Install dependencies: pip install -r requirements.txt
# 2. Start Redis: docker run -d -p 6379:6379 redis:7-alpine
# 3. Copy .env.example to .env and update values
# 4. Run: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# 
# Or use Docker Compose:
# docker-compose up -d
                raise ValueError(f"Service {service_name} not found")
        
        instances = self.services[service_name]
        healthy_instances = [inst for inst in instances if inst.health_score > 0.3]
        
        if not healthy_instances:
            # Fallback to any available instance
            healthy_instances = instances
        
        # Weighted random selection based on health score
        weights = [inst.health_score for inst in healthy_instances]
        selected = random.choices(healthy_instances, weights=weights)[0]
        
        return selected.url
    
    async def health_check(self, service_name: str, instance: ServiceInstance) -> bool:
        """Perform health check on service instance"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{instance.url}/health")
                if response.status_code == 200:
                    instance.health_score = min(1.0, instance.health_score + 0.1)
                    instance.failures = 0
                    return True
                else:
                    raise httpx.HTTPError(f"Health check failed: {response.status_code}")
        
        except Exception:
            instance.failures += 1
            instance.health_score = max(0.0, instance.health_score - 0.2)
            return False
        finally:
            instance.last_check = time.time()
    
    async def record_success(self, service_name: str, url: str):
        """Record successful request to improve health score"""
        for instance in self.services.get(service_name, []):
            if instance.url == url:
                instance.health_score = min(1.0, instance.health_score + 0.05)
                break
    
    async def record_failure(self, service_name: str, url: str):
        """Record failed request to decrease health score"""
        for instance in self.services.get(service_name, []):
            if instance.url == url:
                instance.failures += 1
                instance.health_score = max(0.0, instance.health_score - 0.1)
                break

# =============================================================================
# =============================================================================
# core/middleware.py - Custom Middleware Components
# =============================================================================

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging
import json
import uuid
from typing import Callable

from core.auth import AuthHandler
from core.exceptions import GenoFlowException, AuthenticationError
from core.dependencies import get_redis_client

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global error handling middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
            return response
        
        except GenoFlowException as e:
            logger.error(f"GenoFlow error {request_id}: {e}")
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": e.error_code,
                        "message": e.message,
                        "details": e.details,
                        "request_id": request_id
                    }
                }
            )
        
        except Exception as e:
            logger.exception(f"Unexpected error {request_id}: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An internal server error occurred",
                        "request_id": request_id
                    }
                }
            )

class LoggingMiddleware(BaseHTTPMiddleware):
    """Request/response logging middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        
        # Log request
        logger.info(f"Request {request_id}: {request.method} {request.url}")
        
        # Process request
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"Response {request_id}: {response.status_code} "
            f"({process_time:.3f}s)"
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/redoc"]:
            return await call_next(request)
        
        # Get client identifier (IP or user ID if authenticated)
        client_ip = request.client.host
        auth_header = request.headers.get("authorization")
        
        # Use user ID for authenticated requests, IP for anonymous
        if auth_header and auth_header.startswith("Bearer "):
            try:
                # Simple token decode to get user ID (not full validation)
                import jwt
                from config.settings import get_settings
                settings = get_settings()
                token = auth_header.split(" ")[1]
                payload = jwt.decode(token, options={"verify_signature": False})
                client_id = f"user:{payload.get('sub', client_ip)}"
            except:
                client_id = f"ip:{client_ip}"
        else:
            client_id = f"ip:{client_ip}"
        
        # Check rate limit
        redis_client = await get_redis_client()
        current_minute = int(time.time() // 60)
        key = f"rate_limit:{client_id}:{current_minute}"
        
        try:
            current_count = await redis_client.incr(key)
            if current_count == 1:
                await redis_client.expire(key, 60)  # Expire after 1 minute
            
            from config.settings import get_settings
            settings = get_settings()
            
            if current_count > settings.rate_limit_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests",
                            "retry_after": 60
                        }
                    }
                )
        
        except Exception as e:
            logger.warning(f"Rate limiting error: {e}")
            # Continue on rate limiting errors
        
        return await call_next(request)

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for JWT token validation"""
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health", "/docs", "/redoc", "/openapi.json", "/auth/login", "/auth/refresh", "/"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip authentication for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Extract authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "MISSING_AUTHENTICATION",
                        "message": "Authentication required"
                    }
                }
            )
        
        try:
            # Validate token
            token = auth_header.split(" ")[1]
            redis_client = await get_redis_client()
            from config.settings import get_settings
            settings = get_settings()
            
            auth_handler = AuthHandler(redis_client, settings.jwt_secret, settings.jwt_algorithm)
            user = await auth_handler.verify_token(token)
            
            # Store user in request state
            request.state.current_user = user
            
        except AuthenticationError as e:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTHENTICATION_FAILED",
                        "message": str(e)
                    }
                }
            )
        except Exception as e:
            logger.exception(f"Authentication error: {e}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "AUTHENTICATION_ERROR",
                        "message": "Authentication failed"
                    }
                }
            )
        
        return await call_next(request)

# =============================================================================
# core/exceptions.py - Custom Exception Classes
# =============================================================================

from typing import Dict, Any, Optional

class GenoFlowException(Exception):
    """Base exception for GenoFlow API"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "GENOFLOW_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

class AuthenticationError(GenoFlowException):
    """Authentication related errors"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR"
        )

class AuthorizationError(GenoFlowException):
    """Authorization related errors"""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR"
        )

class ValidationError(GenoFlowException):
    """Validation related errors"""
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details
        )

class ServiceUnavailableError(GenoFlowException):
    """Service unavailable errors"""
    
    def __init__(self, service_name: str):
        super().__init__(
            message=f"Service {service_name} is currently unavailable",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE"
        )

# =============================================================================
# models/user.py - User and Authentication Models
# =============================================================================

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class User(BaseModel):
    user_id: str
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    roles: List[str] = []
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User

class RefreshRequest(BaseModel):
    refresh_token: str

# =============================================================================
# models/responses.py - Standard Response Models
# =============================================================================

from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime

class APIResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: datetime = datetime.utcnow()

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: float
    version: str
    services: Optional[Dict[str, str]] = None

# =============================================================================
# api/routes/auth.py - Authentication Routes
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer

from core.auth import AuthHandler
from core.dependencies import get_auth_handler, get_current_user
from models.user import LoginRequest, TokenResponse, RefreshRequest, User
from core.exceptions import AuthenticationError

auth_router = APIRouter()
security = HTTPBearer()

@auth_router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    auth_handler: AuthHandler = Depends(get_auth_handler)
):
    """Authenticate user and return JWT tokens"""
    try:
        # In production, validate credentials against user service
        # For now, mock user validation
        if credentials.username == "admin" and credentials.password == "password":
            user = User(
                user_id="1",
                username="admin",
                email="admin@genoflow.com",
                roles=["admin"]
            )
        else:
            