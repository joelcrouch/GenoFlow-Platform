# GenoFlow MVC+Services Architecture
## Frontend (Desktop App) + Controller + Data Ingestion Service

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DESKTOP APPLICATION                      │
│                        (View Layer)                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │   Dashboard     │ │  File Upload    │ │   Results     │ │
│  │   Component     │ │   Component     │ │   Viewer      │ │
│  └─────────────────┘ └─────────────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
                        HTTP/REST API
                               │
┌─────────────────────────────────────────────────────────────┐
│                      CONTROLLER LAYER                       │
│                     (API Gateway/Router)                    │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │   Auth Handler  │ │ Request Router  │ │ Response      │ │
│  │                 │ │                 │ │ Formatter     │ │
│  └─────────────────┘ └─────────────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
                        Service Calls
                               │
┌─────────────────────────────────────────────────────────────┐
│                       SERVICE LAYER                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │ Data Ingestion  │ │  Quality Control│ │   Pipeline    │ │
│  │    Service      │ │     Service     │ │   Management  │ │
│  └─────────────────┘ └─────────────────┘ └───────────────┘ │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │ Workflow Exec   │ │ Results Mgmt    │ │ Notification  │ │
│  │    Service      │ │    Service      │ │   Service     │ │
│  └─────────────────┘ └─────────────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

# 1. DESKTOP APPLICATION (Frontend/View Layer)

## Overview
A cross-platform desktop application built with **Electron + React** that provides an intuitive interface for bioinformatics researchers to manage sequencing data processing workflows.

## Technology Stack
- **Framework**: Electron 28+ with React 18+
- **State Management**: Redux Toolkit
- **UI Components**: Material-UI (MUI) or Ant Design
- **File Handling**: Native file system APIs
- **HTTP Client**: Axios with retry logic
- **Authentication**: JWT token management
- **Build Tool**: Webpack 5
- **Package Manager**: npm/yarn

## Core Components

### 1.1 Authentication Component
**Purpose**: Handle user login, token refresh, and session management

**Features**:
- Login form with username/password
- Remember me functionality
- Automatic token refresh
- Session timeout handling
- Multi-factor authentication support

**Props Interface**:
```typescript
interface AuthProps {
  onLoginSuccess: (user: User, token: string) => void;
  onLogout: () => void;
  isAuthenticated: boolean;
}

interface User {
  id: string;
  username: string;
  email: string;
  roles: string[];
  lastLogin: Date;
}
```

### 1.2 Dashboard Component
**Purpose**: Main application hub showing system overview and quick actions

**Features**:
- Active jobs overview with real-time status
- Recent uploads and results
- System health indicators
- Quick action buttons (New Upload, View Results)
- Resource usage charts
- Notification center

**State Structure**:
```typescript
interface DashboardState {
  activeJobs: Job[];
  recentUploads: Upload[];
  systemHealth: HealthMetrics;
  notifications: Notification[];
  loading: boolean;
  error: string | null;
}
```

### 1.3 File Upload Component
**Purpose**: Handle sequencing data file uploads with progress tracking

**Features**:
- Drag-and-drop file selection
- Multi-file upload support
- File format validation (FASTQ, BAM, CRAM)
- Upload progress with pause/resume
- Metadata form (sample ID, project, sequencing type)
- Upload history and retry failed uploads

**Component Structure**:
```typescript
interface FileUploadProps {
  onUploadSuccess: (upload: Upload) => void;
  onUploadError: (error: UploadError) => void;
  acceptedFormats: string[];
  maxFileSize: number;
}

interface UploadProgress {
  uploadId: string;
  fileName: string;
  progress: number;
  status: 'uploading' | 'validating' | 'completed' | 'error';
  speed: number; // bytes per second
  eta: number; // seconds
}
```

### 1.4 Pipeline Configuration Component
**Purpose**: Configure and manage bioinformatics pipeline settings

**Features**:
- Pipeline template selection (WGS, WES, Targeted)
- Parameter configuration with validation
- Resource allocation settings
- Save/load configuration presets
- Pipeline version selection
- Real-time parameter validation

### 1.5 Results Viewer Component
**Purpose**: Display and manage analysis results

**Features**:
- Tabular view of completed jobs
- File download management with progress
- Quality metrics visualization
- Report preview (HTML/PDF)
- Export functionality
- Result sharing capabilities

**Data Interface**:
```typescript
interface ResultsData {
  jobId: string;
  sampleId: string;
  pipelineType: string;
  status: JobStatus;
  files: ResultFile[];
  metrics: QualityMetrics;
  completedAt: Date;
  downloadLinks: DownloadLink[];
}
```

## Application State Management

### Redux Store Structure
```typescript
interface AppState {
  auth: {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
  };
  uploads: {
    active: Upload[];
    history: Upload[];
    progress: { [uploadId: string]: UploadProgress };
  };
  jobs: {
    active: Job[];
    completed: Job[];
    failed: Job[];
  };
  ui: {
    activeView: string;
    notifications: Notification[];
    loading: { [key: string]: boolean };
  };
}
```

## Error Handling Strategy
- Global error boundary for React components
- Automatic retry logic for network requests
- User-friendly error messages with suggested actions
- Offline mode with local caching
- Detailed error logging for debugging

## Security Considerations
- JWT token storage in secure electron store
- Input validation and sanitization
- File upload virus scanning
- Secure communication with HTTPS only
- Session timeout and automatic logout

---

# 2. CONTROLLER LAYER (API Gateway)

## Overview
A lightweight API gateway built with **FastAPI** that handles routing, authentication, and request/response formatting between the frontend and backend services.

## Technology Stack
- **Framework**: FastAPI 0.104+
- **Authentication**: JWT with refresh tokens
- **Validation**: Pydantic models
- **HTTP Client**: httpx for service communication
- **Caching**: Redis for session management
- **Monitoring**: Prometheus metrics
- **Documentation**: Auto-generated OpenAPI/Swagger

## Core Modules

### 2.1 Authentication Handler
**Purpose**: Manage user authentication and authorization

**Responsibilities**:
- JWT token validation and refresh
- Role-based access control (RBAC)
- Session management
- Rate limiting per user
- Audit logging

**Code Structure**:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

class AuthHandler:
    def __init__(self, redis_client, jwt_secret):
        self.redis = redis_client
        self.jwt_secret = jwt_secret
    
    async def verify_token(self, token: str) -> User:
        # Token validation logic
        pass
    
    async def check_permissions(self, user: User, resource: str, action: str) -> bool:
        # RBAC logic
        pass
    
    async def refresh_token(self, refresh_token: str) -> TokenPair:
        # Token refresh logic
        pass
```

### 2.2 Request Router
**Purpose**: Route requests to appropriate backend services

**Features**:
- Dynamic service discovery
- Load balancing between service instances
- Circuit breaker pattern for service failures
- Request/response logging
- Health check integration

**Router Configuration**:
```python
from fastapi import APIRouter
from typing import Dict, List

class ServiceRouter:
    def __init__(self):
        self.service_registry: Dict[str, List[str]] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    async def route_request(self, service_name: str, endpoint: str, **kwargs):
        # Service routing logic with failover
        pass
    
    def register_service(self, name: str, urls: List[str]):
        # Service registration
        pass
```

### 2.3 Response Formatter
**Purpose**: Standardize API responses and error handling

**Features**:
- Consistent response structure
- Error code mapping
- Response compression
- CORS handling
- API versioning support

**Response Models**:
```python
from pydantic import BaseModel
from typing import Optional, Any, Dict

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    request_id: str
    timestamp: str

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: str
```

## API Endpoints

### Authentication Endpoints
```python
@router.post("/auth/login")
async def login(credentials: LoginRequest) -> TokenResponse:
    # Authentication logic
    pass

@router.post("/auth/refresh")
async def refresh_token(refresh_request: RefreshRequest) -> TokenResponse:
    # Token refresh logic
    pass

@router.post("/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):
    # Logout logic
    pass
```

### Data Ingestion Proxy Endpoints
```python
@router.post("/api/v1/ingestion/upload")
async def upload_file(
    file: UploadFile,
    metadata: UploadMetadata,
    current_user: User = Depends(get_current_user)
) -> UploadResponse:
    # Proxy to data ingestion service
    pass

@router.get("/api/v1/ingestion/upload/{upload_id}")
async def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_user)
) -> UploadStatusResponse:
    # Proxy to data ingestion service
    pass
```

## Configuration Management
```python
from pydantic import BaseSettings

class ControllerSettings(BaseSettings):
    # Service URLs
    data_ingestion_service_url: str
    qc_service_url: str
    pipeline_service_url: str
    
    # Authentication
    jwt_secret: str
    jwt_expiry_minutes: int = 60
    
    # Redis
    redis_url: str
    
    # Rate limiting
    rate_limit_per_minute: int = 100
    
    class Config:
        env_file = ".env"
```

## Middleware Stack
1. **CORS Middleware**: Handle cross-origin requests
2. **Authentication Middleware**: Validate JWT tokens
3. **Rate Limiting Middleware**: Prevent API abuse
4. **Logging Middleware**: Request/response logging
5. **Compression Middleware**: Gzip response compression
6. **Error Handling Middleware**: Global exception handling

---

# 3. DATA INGESTION SERVICE

## Overview
A robust microservice built with **FastAPI + Celery** that handles secure file uploads, validation, and initial processing of sequencing data files.

## Technology Stack
- **Framework**: FastAPI 0.104+
- **Task Queue**: Celery with Redis broker
- **File Storage**: AWS S3 with multipart upload
- **Database**: PostgreSQL for metadata
- **Validation**: BioPython for file format validation
- **Monitoring**: Prometheus metrics + structured logging
- **Containerization**: Docker with multi-stage builds

## Core Components

### 3.1 File Upload Handler
**Purpose**: Manage large file uploads with resumable capability

**Features**:
- Multipart upload to S3 with resume capability
- File integrity validation (checksums)
- Concurrent upload streams
- Upload progress tracking
- Automatic cleanup of failed uploads

**Implementation**:
```python
from fastapi import UploadFile, BackgroundTasks
from botocore.exceptions import ClientError
import hashlib
import asyncio

class FileUploadHandler:
    def __init__(self, s3_client, bucket_name: str):
        self.s3_client = s3_client
        self.bucket = bucket_name
    
    async def create_multipart_upload(self, file_name: str, metadata: dict) -> str:
        """Initialize multipart upload and return upload_id"""
        response = await self.s3_client.create_multipart_upload(
            Bucket=self.bucket,
            Key=file_name,
            Metadata=metadata,
            ServerSideEncryption='AES256'
        )
        return response['UploadId']
    
    async def upload_part(self, upload_id: str, part_number: int, 
                         file_data: bytes) -> dict:
        """Upload a single part of multipart upload"""
        response = await self.s3_client.upload_part(
            Bucket=self.bucket,
            Key=file_name,
            PartNumber=part_number,
            UploadId=upload_id,
            Body=file_data
        )
        return {
            'PartNumber': part_number,
            'ETag': response['ETag']
        }
    
    async def complete_multipart_upload(self, upload_id: str, 
                                      parts: list) -> str:
        """Complete multipart upload and return final S3 URL"""
        await self.s3_client.complete_multipart_upload(
            Bucket=self.bucket,
            Key=file_name,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )
        return f"s3://{self.bucket}/{file_name}"
```

### 3.2 File Validation Engine
**Purpose**: Validate sequencing file formats and extract metadata

**Supported Formats**:
- FASTQ (single/paired-end, compressed/uncompressed)
- BAM/CRAM alignment files
- VCF variant files
- Basic metadata validation

**Validation Rules**:
```python
from Bio import SeqIO
from pysam import AlignmentFile
import gzip
from typing import Dict, List, Tuple

class FileValidator:
    def __init__(self):
        self.supported_formats = {
            'fastq': ['.fastq', '.fq', '.fastq.gz', '.fq.gz'],
            'bam': ['.bam'],
            'cram': ['.cram'],
            'vcf': ['.vcf', '.vcf.gz']
        }
    
    async def validate_fastq(self, file_path: str) -> ValidationResult:
        """Validate FASTQ file format and extract basic stats"""
        try:
            # Handle gzipped files
            opener = gzip.open if file_path.endswith('.gz') else open
            mode = 'rt' if file_path.endswith('.gz') else 'r'
            
            read_count = 0
            total_length = 0
            quality_scores = []
            
            with opener(file_path, mode) as handle:
                for i, record in enumerate(SeqIO.parse(handle, "fastq")):
                    read_count += 1
                    total_length += len(record.seq)
                    
                    # Sample quality scores from first 1000 reads
                    if i < 1000:
                        quality_scores.extend(record.letter_annotations["phred_quality"])
                    
                    # Early termination for large files (just validate format)
                    if i > 10000:
                        break
            
            return ValidationResult(
                is_valid=True,
                file_type='fastq',
                metadata={
                    'read_count': read_count,
                    'avg_read_length': total_length / read_count if read_count > 0 else 0,
                    'avg_quality': sum(quality_scores) / len(quality_scores) if quality_scores else 0
                }
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=str(e)
            )
    
    async def validate_bam(self, file_path: str) -> ValidationResult:
        """Validate BAM/CRAM file and extract header info"""
        try:
            with AlignmentFile(file_path, "rb") as bam_file:
                header = bam_file.header
                
                # Count first 1000 reads for stats
                read_count = 0
                mapped_count = 0
                
                for read in bam_file:
                    read_count += 1
                    if not read.is_unmapped:
                        mapped_count += 1
                    
                    if read_count >= 1000:
                        break
                
                return ValidationResult(
                    is_valid=True,
                    file_type='bam',
                    metadata={
                        'reference_sequences': len(header.references),
                        'sample_reads_checked': read_count,
                        'mapping_rate': mapped_count / read_count if read_count > 0 else 0,
                        'reference_names': header.references[:10]  # First 10 references
                    }
                )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=str(e)
            )
```

### 3.3 Metadata Management
**Purpose**: Store and manage file metadata and upload tracking

**Database Schema**:
```sql
-- Upload tracking table
CREATE TABLE uploads (
    upload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size BIGINT,
    file_type VARCHAR(50),
    s3_path VARCHAR(500),
    upload_status VARCHAR(50) DEFAULT 'initiated',
    validation_status VARCHAR(50) DEFAULT 'pending',
    checksum_md5 VARCHAR(32),
    checksum_sha256 VARCHAR(64),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Sample metadata table
CREATE TABLE samples (
    sample_id VARCHAR(100) PRIMARY KEY,
    project_id VARCHAR(100) NOT NULL,
    patient_id VARCHAR(100),
    sample_type VARCHAR(50),
    sequencing_platform VARCHAR(50),
    library_prep VARCHAR(100),
    sequencing_date DATE,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- File validation results
CREATE TABLE validation_results (
    validation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id UUID REFERENCES uploads(upload_id),
    validation_type VARCHAR(50),
    is_valid BOOLEAN,
    validation_metrics JSONB,
    error_messages TEXT[],
    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.4 Background Task Processing
**Purpose**: Handle long-running validation and processing tasks

**Celery Tasks**:
```python
from celery import Celery
from .validation import FileValidator
from .storage import S3Handler

celery_app = Celery('data_ingestion')

@celery_app.task(bind=True, max_retries=3)
def validate_uploaded_file(self, upload_id: str, file_path: str):
    """Asynchronously validate uploaded file"""
    try:
        validator = FileValidator()
        
        # Update status to processing
        update_upload_status(upload_id, 'validating')
        
        # Perform validation based on file type
        file_type = detect_file_type(file_path)
        
        if file_type == 'fastq':
            result = await validator.validate_fastq(file_path)
        elif file_type in ['bam', 'cram']:
            result = await validator.validate_bam(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # Store validation results
        store_validation_result(upload_id, result)
        
        if result.is_valid:
            update_upload_status(upload_id, 'completed')
            # Trigger next stage (QC analysis)
            trigger_qc_analysis.delay(upload_id)
        else:
            update_upload_status(upload_id, 'validation_failed')
            
    except Exception as exc:
        update_upload_status(upload_id, 'error')
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

@celery_app.task
def cleanup_failed_uploads():
    """Periodic task to clean up incomplete uploads"""
    # Find uploads older than 24 hours that are still in progress
    # Delete S3 objects and database records
    pass
```

## API Endpoints

### Upload Endpoints
```python
from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import List

router = APIRouter(prefix="/ingestion", tags=["data-ingestion"])

@router.post("/upload", response_model=UploadResponse)
async def upload_sequencing_file(
    file: UploadFile = File(...),
    sample_id: str = Form(...),
    project_id: str = Form(...),
    sample_metadata: str = Form(None),  # JSON string
    checksum: str = Form(None),
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Upload sequencing data file with metadata
    
    - **file**: Sequencing data file (FASTQ, BAM, CRAM)
    - **sample_id**: Unique sample identifier
    - **project_id**: Project identifier
    - **sample_metadata**: Additional sample metadata as JSON
    - **checksum**: Optional file checksum for integrity verification
    """
    
    # Validate file size and type
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large")
    
    if not is_supported_format(file.filename):
        raise HTTPException(400, "Unsupported file format")
    
    # Create upload record
    upload = await create_upload_record(
        user_id=current_user.id,
        filename=file.filename,
        sample_id=sample_id,
        project_id=project_id,
        file_size=file.size
    )
    
    # Start multipart upload to S3
    s3_path = f"uploads/{current_user.id}/{upload.upload_id}/{file.filename}"
    upload_handler = FileUploadHandler(s3_client, UPLOAD_BUCKET)
    
    try:
        # Upload file to S3
        s3_url = await upload_handler.upload_large_file(file, s3_path)
        
        # Update upload record
        await update_upload_record(upload.upload_id, {
            's3_path': s3_url,
            'upload_status': 'uploaded'
        })
        
        # Schedule background validation
        background_tasks.add_task(
            validate_uploaded_file.delay,
            upload.upload_id,
            s3_path
        )
        
        return UploadResponse(
            upload_id=upload.upload_id,
            status='uploaded',
            s3_path=s3_url,
            validation_status='pending'
        )
        
    except Exception as e:
        await update_upload_record(upload.upload_id, {
            'upload_status': 'failed',
            'error_message': str(e)
        })
        raise HTTPException(500, f"Upload failed: {str(e)}")

@router.get("/upload/{upload_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get upload status and validation results"""
    
    upload = await get_upload_by_id(upload_id)
    
    if not upload:
        raise HTTPException(404, "Upload not found")
    
    if upload.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(403, "Access denied")
    
    # Get validation results if available
    validation_result = await get_validation_result(upload_id)
    
    return UploadStatusResponse(
        upload_id=upload_id,
        filename=upload.original_filename,
        status=upload.upload_status,
        validation_status=upload.validation_status,
        file_size=upload.file_size,
        validation_results=validation_result.metadata if validation_result else None,
        created_at=upload.created_at,
        completed_at=upload.completed_at
    )

@router.get("/uploads", response_model=List[UploadSummary])
async def list_user_uploads(
    limit: int = 50,
    offset: int = 0,
    status: str = None,
    current_user: User = Depends(get_current_user)
):
    """List user's uploads with optional filtering"""
    
    uploads = await get_user_uploads(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        status_filter=status
    )
    
    return [
        UploadSummary(
            upload_id=upload.upload_id,
            filename=upload.original_filename,
            sample_id=upload.sample_id,
            status=upload.upload_status,
            file_size=upload.file_size,
            created_at=upload.created_at
        ) for upload in uploads
    ]
```

## Error Handling and Monitoring

### Error Categories
1. **Validation Errors**: Invalid file format, corrupted data
2. **Storage Errors**: S3 upload failures, disk space issues
3. **Authentication Errors**: Invalid tokens, insufficient permissions
4. **Rate Limiting**: Too many concurrent uploads
5. **System Errors**: Database connectivity, service unavailability

### Monitoring Metrics
```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
upload_requests_total = Counter('upload_requests_total', 'Total upload requests', ['status'])
upload_duration = Histogram('upload_duration_seconds', 'Upload duration')
active_uploads = Gauge('active_uploads', 'Number of active uploads')
validation_duration = Histogram('validation_duration_seconds', 'File validation duration', ['file_type'])
```

## Configuration and Deployment

### Environment Configuration
```yaml
# docker-compose.yml for development
version: '3.8'
services:
  data-ingestion-api:
    build: .
    ports:
      - "8001:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/genoflow
      - REDIS_URL=redis://redis:6379
      - AWS_REGION=us-east-1
      - S3_UPLOAD_BUCKET=genoflow-uploads
      - MAX_FILE_SIZE=50GB
    depends_on:
      - db
      - redis
  
  data-ingestion-worker:
    build: .
    command: celery -A app.celery worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/genoflow
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=genoflow
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

This architecture provides clear separation of concerns, allowing each team to work independently while maintaining clean interfaces between components. The desktop app team can focus on UI/UX, the controller team on API orchestration, and the data ingestion team on robust file handling and validation.