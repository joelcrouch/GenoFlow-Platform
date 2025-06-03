# api_client.py
import requests
import threading
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Callable
from PySide6.QtCore import QObject, pyqtSignal, QTimer
import logging

class APIClient(QObject):
    """Complete GenoFlow API client for desktop application"""
    
    # Signals for UI updates
    upload_progress = pyqtSignal(str, int)  # file_id, percentage
    job_status_updated = pyqtSignal(str, dict)  # job_id, status_data
    error_occurred = pyqtSignal(str)  # error_message
    file_validated = pyqtSignal(str, dict)  # file_id, validation_results
    download_progress = pyqtSignal(str, int)  # download_id, percentage
    system_status_updated = pyqtSignal(dict)  # system_status
    
    def __init__(self, base_url="https://api.genoflow-mvp.com/v1", api_key=None):
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        # Configure session
        if api_key:
            self.session.headers.update({"X-API-Key": api_key})
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "GenoFlow-Desktop/1.0.0"
        })
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Active uploads and downloads tracking
        self._active_uploads = {}
        self._active_downloads = {}
        
        # Status monitoring timer
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._check_system_status)
        self._status_timer.start(30000)  # Check every 30 seconds
    
    def set_api_key(self, api_key: str):
        """Update API key"""
        self.api_key = api_key
        self.session.headers.update({"X-API-Key": api_key})
    
    def _handle_response(self, response: requests.Response) -> Dict:
        """Handle API response with error checking"""
        try:
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('error', {}).get('message', f"HTTP {response.status_code}")
                self.error_occurred.emit(f"API Error: {error_msg}")
                return None
            return response.json()
        except json.JSONDecodeError:
            self.error_occurred.emit(f"Invalid JSON response from API")
            return None
        except Exception as e:
            self.error_occurred.emit(f"Request failed: {str(e)}")
            return None
    
    # =================================================================
    # FILE INGESTION API
    # =================================================================
    
    def upload_file_async(self, file_path: str, sample_id: str, project_id: Optional[str] = None):
        """Upload FASTQ file asynchronously"""
        file_path = Path(file_path)
        if not file_path.exists():
            self.error_occurred.emit(f"File not found: {file_path}")
            return
        
        thread = threading.Thread(
            target=self._upload_file_worker,
            args=(str(file_path), sample_id, project_id)
        )
        thread.daemon = True
        thread.start()
    
    def _upload_file_worker(self, file_path: str, sample_id: str, project_id: Optional[str] = None):
        """Background worker for file upload with progress tracking"""
        file_id = f"upload_{datetime.now().timestamp()}"
        
        try:
            file_size = os.path.getsize(file_path)
            uploaded = 0
            
            def upload_callback(chunk):
                nonlocal uploaded
                uploaded += len(chunk)
                progress = int((uploaded / file_size) * 100)
                self.upload_progress.emit(file_id, progress)
                return chunk
            
            with open(file_path, 'rb') as f:
                # Wrap file for progress tracking
                class ProgressFile:
                    def __init__(self, file_obj, callback):
                        self.file_obj = file_obj
                        self.callback = callback
                    
                    def read(self, size=-1):
                        chunk = self.file_obj.read(size)
                        if chunk:
                            self.callback(chunk)
                        return chunk
                    
                    def __getattr__(self, attr):
                        return getattr(self.file_obj, attr)
                
                progress_file = ProgressFile(f, upload_callback)
                
                files = {'file': (Path(file_path).name, progress_file, 'application/octet-stream')}
                data = {'sample_id': sample_id}
                if project_id:
                    data['project_id'] = project_id
                
                response = self.session.post(
                    f"{self.base_url}/files/upload",
                    files=files,
                    data=data,
                    timeout=3600  # 1 hour timeout for large files
                )
                
                result = self._handle_response(response)
                if result:
                    self.upload_progress.emit(file_id, 100)
                    # Start monitoring file validation
                    self._monitor_file_validation(result['file_id'])
                    
        except Exception as e:
            self.error_occurred.emit(f"Upload error: {str(e)}")
    
    def get_file_status(self, file_id: str) -> Optional[Dict]:
        """Get file upload and validation status"""
        try:
            response = self.session.get(f"{self.base_url}/files/{file_id}")
            return self._handle_response(response)
        except Exception as e:
            self.error_occurred.emit(f"Failed to get file status: {str(e)}")
            return None
    
    def _monitor_file_validation(self, file_id: str):
        """Monitor file validation in background"""
        def validation_worker():
            max_attempts = 60  # 5 minutes with 5-second intervals
            attempts = 0
            
            while attempts < max_attempts:
                status_data = self.get_file_status(file_id)
                if status_data:
                    if status_data['status'] in ['ready', 'error']:
                        self.file_validated.emit(file_id, status_data)
                        break
                threading.Event().wait(5)  # Wait 5 seconds
                attempts += 1
        
        thread = threading.Thread(target=validation_worker)
        thread.daemon = True
        thread.start()
    
    # =================================================================
    # PIPELINE MANAGER API
    # =================================================================
    
    def get_pipelines(self) -> Optional[List[Dict]]:
        """Get list of available pipelines"""
        try:
            response = self.session.get(f"{self.base_url}/pipelines")
            result = self._handle_response(response)
            return result['pipelines'] if result else None
        except Exception as e:
            self.error_occurred.emit(f"Failed to get pipelines: {str(e)}")
            return None
    
    def get_pipeline_details(self, pipeline_id: str) -> Optional[Dict]:
        """Get detailed information about a specific pipeline"""
        try:
            response = self.session.get(f"{self.base_url}/pipelines/{pipeline_id}")
            return self._handle_response(response)
        except Exception as e:
            self.error_occurred.emit(f"Failed to get pipeline details: {str(e)}")
            return None
    
    # =================================================================
    # JOB EXECUTION API
    # =================================================================
    
    def submit_job(self, pipeline_id: str, sample_id: str, file_ids: List[str], 
                   parameters: Optional[Dict] = None) -> Optional[Dict]:
        """Submit a new pipeline job"""
        try:
            data = {
                'pipeline_id': pipeline_id,
                'sample_id': sample_id,
                'file_ids': file_ids,
                'parameters': parameters or {}
            }
            
            response = self.session.post(
                f"{self.base_url}/jobs",
                json=data
            )
            
            result = self._handle_response(response)
            if result:
                # Start monitoring job status
                self._monitor_job_status(result['job_id'])
            return result
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to submit job: {str(e)}")
            return None
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get current job status and progress"""
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}")
            return self._handle_response(response)
        except Exception as e:
            self.error_occurred.emit(f"Failed to get job status: {str(e)}")
            return None
    
    def list_jobs(self, status: Optional[str] = None, sample_id: Optional[str] = None, 
                  limit: int = 50, page: int = 1) -> Optional[Dict]:
        """List jobs with optional filters"""
        try:
            params = {'limit': limit, 'page': page}
            if status:
                params['status'] = status
            if sample_id:
                params['sample_id'] = sample_id
            
            response = self.session.get(f"{self.base_url}/jobs", params=params)
            return self._handle_response(response)
        except Exception as e:
            self.error_occurred.emit(f"Failed to list jobs: {str(e)}")
            return None
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or queued job"""
        try:
            response = self.session.delete(f"{self.base_url}/jobs/{job_id}")
            return response.status_code == 200
        except Exception as e:
            self.error_occurred.emit(f"Failed to cancel job: {str(e)}")
            return False
    
    def _monitor_job_status(self, job_id: str):
        """Monitor job status changes in background"""
        def status_worker():
            last_status = None
            max_attempts = 2880  # 24 hours with 30-second intervals
            attempts = 0
            
            while attempts < max_attempts:
                status_data = self.get_job_status(job_id)
                if status_data:
                    current_status = status_data['status']
                    if current_status != last_status:
                        self.job_status_updated.emit(job_id, status_data)
                        last_status = current_status
                        
                        # Stop monitoring if job is complete
                        if current_status in ['completed', 'failed']:
                            break
                
                threading.Event().wait(30)  # Wait 30 seconds
                attempts += 1
        
        thread = threading.Thread(target=status_worker)
        thread.daemon = True
        thread.start()
    
    # =================================================================
    # RESULTS STORAGE API
    # =================================================================
    
    def get_job_results(self, job_id: str) -> Optional[Dict]:
        """Get job results and output files"""
        try:
            response = self.session.get(f"{self.base_url}/results/{job_id}")
            return self._handle_response(response)
        except Exception as e:
            self.error_occurred.emit(f"Failed to get job results: {str(e)}")
            return None
    
    def generate_download_urls(self, job_id: str, file_type: str = "all", 
                             expiration_hours: int = 24) -> Optional[List[Dict]]:
        """Generate secure download URLs for result files"""
        try:
            data = {
                'file_type': file_type,
                'expiration_hours': expiration_hours
            }
            
            response = self.session.post(
                f"{self.base_url}/results/{job_id}/download",
                json=data
            )
            
            result = self._handle_response(response)
            return result['download_urls'] if result else None
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to generate download URLs: {str(e)}")
            return None
    
    def download_file_async(self, download_url: str, local_path: str, 
                           callback: Optional[Callable] = None):
        """Download file asynchronously with progress tracking"""
        thread = threading.Thread(
            target=self._download_file_worker,
            args=(download_url, local_path, callback)
        )
        thread.daemon = True
        thread.start()
    
    def _download_file_worker(self, download_url: str, local_path: str, 
                            callback: Optional[Callable] = None):
        """Background worker for file download"""
        download_id = f"download_{datetime.now().timestamp()}"
        
        try:
            response = self.session.get(download_url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            local_path = Path(local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            downloaded = 0
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.download_progress.emit(download_id, progress)
            
            if callback:
                callback(str(local_path))
                
        except Exception as e:
            self.error_occurred.emit(f"Download error: {str(e)}")
    
    # =================================================================
    # SYSTEM STATUS API
    # =================================================================
    
    def get_system_health(self) -> Optional[Dict]:
        """Get system health and status"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return self._handle_response(response)
        except Exception as e:
            self.error_occurred.emit(f"Failed to get system health: {str(e)}")
            return None
    
    def _check_system_status(self):
        """Periodic system status check"""
        def status_worker():
            health_data = self.get_system_health()
            if health_data:
                self.system_status_updated.emit(health_data)
        
        thread = threading.Thread(target=status_worker)
        thread.daemon = True
        thread.start()
    
    # =================================================================
    # UTILITY METHODS
    # =================================================================
    
    def test_connection(self) -> bool:
        """Test API connection and authentication"""
        try:
            health_data = self.get_system_health()
            return health_data is not None
        except:
            return False
    
    def get_active_jobs_count(self) -> int:
        """Get count of active (running/queued) jobs"""
        jobs_data = self.list_jobs(limit=1)
        if jobs_data and 'stats' in jobs_data:
            return jobs_data['stats'].get('active_jobs', 0)
        return 0
    
    def get_sample_history(self, sample_id: str) -> Optional[List[Dict]]:
        """Get processing history for a specific sample"""
        jobs_data = self.list_jobs(sample_id=sample_id, limit=100)
        return jobs_data['jobs'] if jobs_data else None
    
    def estimate_job_cost(self, pipeline_id: str, file_ids: List[str]) -> Optional[Dict]:
        """Estimate job execution cost (if supported by API)"""
        # This would be implemented when the API supports cost estimation
        # For now, return None
        return None
    
    def cleanup(self):
        """Cleanup resources and stop timers"""
        if self._status_timer:
            self._status_timer.stop()
        self.session.close()
