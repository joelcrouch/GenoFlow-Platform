# GenoFlow API Gateway - Complete Setup Guide

## Project Structure

```
genoflow-api-gateway/
├── main.py                     # FastAPI application entry point
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
├── .env                       # Environment variables (create from .env.example)
├── Dockerfile                 # Docker container configuration
├── docker-compose.yml         # Local development setup
├── README.md                  # Project documentation
│
├── config/
│   ├── __init__.py
│   └── settings.py            # Application configuration
│
├── core/
│   ├── __init__.py
│   ├── auth.py                # Authentication handler
│   ├── dependencies.py        # Dependency injection
│   ├── exceptions.py          # Custom exceptions
│   ├── middleware.py          # Custom middleware
│   ├── monitoring.py          # Prometheus metrics
│   └── service_registry.py    # Service discovery
│
├── models/
│   ├── __init__.py
│   ├── user.py                # User-related models
│   └── responses.py           # Response models
│
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       ├── auth.py            # Authentication endpoints
│       ├── ingestion.py       # Data ingestion endpoints
│       ├── qc.py              # Quality control endpoints
│       ├── pipeline.py        # Pipeline management endpoints
│       ├── execution.py       # Workflow execution endpoints
│       ├── results.py         # Results management endpoints
│       └── monitoring.py      # Monitoring endpoints
│
└── tests/                     # Unit and integration tests
    ├── __init__.py
    ├── test_auth.py
    ├── test_routes.py
    └── conftest.py
```

## Quick Start Guide

### 1. Prerequisites

- Python 3.11+
- Redis (for caching and session management)
- Docker and Docker Compose (optional, for containerized setup)

### 2. Installation Steps

#### Option A: Local Development Setup

```bash
# 1. Clone or create the project directory
mkdir genoflow-api-gateway
cd genoflow-api-gateway

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Redis (using Docker)
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 5. Setup environment variables
cp .env.example .env
# Edit .env file with your configuration

# 6. Run the application
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Option B: Docker Compose Setup

```bash
# 1. Clone or create the project directory
mkdir genoflow-api-gateway
cd genoflow-api-gateway

# 2. Create all the files from the previous artifact

# 3. Start all services
docker-compose up -d

# 4. View logs
docker-compose logs -f api-gateway
```

### 3. Environment Configuration

Create a `.env` file with the following variables:

```env
# JWT Configuration
JWT_SECRET=your-super-secret-jwt-key-change-this-in-production

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Service URLs (update these to match your backend services)
DATA_INGESTION_SERVICE_URL=http://localhost:8001
QC_SERVICE_URL=http://localhost:8002
PIPELINE_SERVICE_URL=http://localhost:8003
EXECUTION_SERVICE_URL=http://localhost:8004
RESULTS_SERVICE_URL=http://localhost:8005
MONITORING_SERVICE_URL=http://localhost:8006
AUTH_SERVICE_URL=http://localhost:8007

# Application Configuration
DEBUG=true
HOST=0.0.0.0
PORT=8000

# CORS Settings
ALLOWED_ORIGINS=["http://localhost:3000", "https://your-frontend-domain.com"]

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_BURST=200
```

### 4. Testing the Setup

Once the application is running, you can test it:

```bash
# Health check
curl http://localhost:8000/health

# API documentation
# Open in browser: http://localhost:8000/docs

# Test authentication
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'
```

## Key Features Implemented

### 🔐 Authentication & Authorization
- JWT token-based authentication
- Refresh token mechanism
- Role-based access control (RBAC)
- Session management with Redis

### 🚦 API Gateway Functionality
- Request routing to backend services
- Service discovery and load balancing
- Circuit breaker pattern for resilience
- Health checking of backend services

### 🛡️ Security & Middleware
- Rate limiting per user/IP
- CORS handling
- Request/response logging
- Global error handling
- Input validation with Pydantic

### 📊 Monitoring & Observability
- Prometheus metrics collection
- Request tracking and performance monitoring
- Structured logging
- Health check endpoints

### 🔧 Configuration Management
- Environment-based configuration
- Centralized settings management
- Feature flags support

## API Endpoints Overview

### Authentication
- `POST /auth/login` - User authentication
- `POST /auth/refresh` - Token refresh
- `POST /auth/logout` - User logout
- `GET /auth/me` - Current user info

### Data Ingestion
- `POST /api/v1/ingestion/upload` - Upload sequencing data
- `GET /api/v1/ingestion/upload/{upload_id}` - Get upload status

### Quality Control
- `POST /api/v1/qc/analyze` - Initiate QC analysis
- `GET /api/v1/qc/results/{qc_job_id}` - Get QC results

### Pipeline Management
- `GET /api/v1/pipelines` - List available pipelines
- `POST /api/v1/pipelines/{pipeline_id}/configurations` - Create pipeline config

### Workflow Execution
- `POST /api/v1/execution/jobs` - Submit pipeline job
- `GET /api/v1/execution/jobs/{job_id}` - Get job status

### Results Management
- `GET /api/v1/results/{job_id}` - Get analysis results
- `POST /api/v1/results/{job_id}/download-links` - Generate download links

### Monitoring
- `GET /api/v1/monitoring/metrics` - Get system metrics
- `GET /metrics` - Prometheus metrics endpoint

## Architecture Highlights

### Modular Design
- Clean separation of concerns
- Dependency injection pattern
- Configurable middleware stack
- Extensible routing system

### Resilience Patterns
- Circuit breaker for service failures
- Automatic retry logic
- Health monitoring and recovery
- Graceful degradation

### Scalability Features
- Async/await throughout the codebase
- Connection pooling for Redis and HTTP clients
- Efficient request routing
- Resource monitoring and alerting

## Development Workflow

### Adding New Routes
1. Create route module in `api/routes/`
2. Define Pydantic models in `models/`
3. Add service URL to configuration
4. Register router in `main.py`
5. Add tests in `tests/`

### Adding New Middleware
1. Create middleware class in `core/middleware.py`
2. Register in `main.py` middleware stack
3. Configure order (order matters!)

### Adding New Services
1. Add service URL to `config/settings.py`
2. Register service in `ServiceRegistry.initialize()`
3. Create proxy endpoints in appropriate route module

## Production Considerations

### Security
- Change JWT secret to a strong, random value
- Use HTTPS in production
- Configure proper CORS origins
- Enable rate limiting
- Set up proper logging levels

### Performance
- Use Redis cluster for high availability
- Configure connection pooling
- Monitor resource usage
- Set up proper caching strategies

### Monitoring
- Set up log aggregation (ELK stack)
- Configure alerts for critical metrics
- Monitor service health
- Track business metrics

### Deployment
- Use container orchestration (Kubernetes)
- Set up CI/CD pipeline
- Configure environment-specific settings
- Plan for zero-downtime deployments

## Extending the Gateway

The architecture is designed to be easily extensible:

- **New Backend Services**: Add URL to config and register in service registry
- **New Authentication Methods**: Extend `AuthHandler` class
- **New Middleware**: Add to middleware stack with proper ordering
- **New Monitoring**: Extend Prometheus metrics or add new monitoring systems
- **New Configuration**: Add to `Settings` class with environment variable support

This FastAPI gateway provides a solid foundation for your GenoFlow clinical sequencing pipeline system with enterprise-grade features for security, monitoring, and scalability.