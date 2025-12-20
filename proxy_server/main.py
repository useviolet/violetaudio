"""
Enhanced Proxy Server for Bittensor Audio Processing Subnet
Integrates database, file management, workflow orchestration, and API endpoints
"""

import asyncio
import json
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, File, UploadFile, Form, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel, Field, validator, ConfigDict
import uvicorn
import os
from pathlib import Path
import warnings
# Suppress Pydantic model_id warnings
warnings.filterwarnings("ignore", message=".*Field.*model_id.*has conflict with protected namespace.*")

# Import our custom modules
from database.enhanced_schema import (
    TaskStatus, TaskPriority, TaskType, TaskModel, 
    MinerInfo, FileReference, TextContent, COLLECTIONS, DatabaseOperations,
    generate_text_content_id
)
from managers.task_manager import TaskManager
from managers.file_manager import FileManager
from managers.miner_response_handler import MinerResponseHandler
from orchestrators.workflow_orchestrator import WorkflowOrchestrator
from api.validator_integration import ValidatorIntegrationAPI
from api.miner_metrics_api import MinerMetricsAPI
from api.leaderboard_api import LeaderboardAPI

# Import AuthMiddleware for type hints (lazy import to avoid circular dependencies)
try:
    from middleware.auth_middleware import AuthMiddleware
except ImportError:
    # Fallback for type checking - will be imported when needed
    AuthMiddleware = None  # type: ignore

def create_safe_filename(original_filename: str) -> str:
    """Create a safe filename for storage by removing problematic characters"""
    import re
    # Handle None or empty filename
    if not original_filename:
        return "unnamed_file.wav"
    
    # Ensure filename is a string (handle bytes if needed)
    if isinstance(original_filename, bytes):
        try:
            original_filename = original_filename.decode('utf-8', errors='replace')
        except:
            original_filename = "unnamed_file.wav"
    
    # Remove or replace problematic characters
    safe_filename = re.sub(r'[^\w\s\-_.]', '_', original_filename)
    # Replace spaces with underscores
    safe_filename = safe_filename.replace(' ', '_')
    # Ensure it's not empty
    if not safe_filename:
        safe_filename = "unnamed_file.wav"
    return safe_filename

# Simple in-memory cache for frequently accessed data
class SimpleCache:
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
        self.access_times = {}
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            # Check if expired
            if datetime.now().timestamp() - self.access_times[key] > self.ttl:
                del self.cache[key]
                del self.access_times[key]
                return None
            
            # Update access time
            self.access_times[key] = datetime.now().timestamp()
            return self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        # Remove oldest if cache is full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
        
        self.cache[key] = value
        self.access_times[key] = datetime.now().timestamp()
    
    def invalidate(self, key: str):
        if key in self.cache:
            del self.cache[key]
            del self.access_times[key]
    
    def clear(self):
        self.cache.clear()
        self.access_times.clear()

# Initialize cache
cache = SimpleCache(max_size=500, ttl=60)  # 500 items, 60 seconds TTL

# System metrics collection
class SystemMetrics:
    def __init__(self):
        self.start_time = datetime.now()
        self.total_requests = 0
        self.total_tasks = 0
        self.total_miner_responses = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.database_operations = 0
        self.errors = 0
    
    def increment_requests(self):
        self.total_requests += 1
    
    def increment_tasks(self):
        self.total_tasks += 1
    
    def increment_miner_responses(self):
        self.total_miner_responses += 1
    
    def increment_cache_hits(self):
        self.cache_hits += 1
    
    def increment_cache_misses(self):
        self.cache_misses += 1
    
    def increment_database_operations(self):
        self.database_operations += 1
    
    def increment_errors(self):
        self.errors += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "uptime_seconds": uptime,
            "uptime_hours": uptime / 3600,
            "total_requests": self.total_requests,
            "total_tasks": self.total_tasks,
            "total_miner_responses": self.total_miner_responses,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            "database_operations": self.database_operations,
            "errors": self.errors,
            "requests_per_second": self.total_requests / uptime if uptime > 0 else 0,
            "tasks_per_second": self.total_tasks / uptime if uptime > 0 else 0,
            "timestamp": datetime.now().isoformat()
        }

# Initialize system metrics
system_metrics = SystemMetrics()

# Weights & Biases integration for monitoring
import wandb
from typing import Dict, Any, Optional, List
import os
from wandb_config import setup_wandb, get_wandb_config

class WandbMonitor:
    def __init__(self, project_name: str = "bittensor-subnet", entity: str = None):
        self.project_name = project_name
        self.entity = entity
        self.run = None
        self.initialized = False
        
        # Setup wandb automatically
        if setup_wandb():
            try:
                # Get configuration
                config = get_wandb_config()
                
                # Initialize wandb with automatic configuration
                self.run = wandb.init(
                    project=config["project"],
                    entity=config["entity"],
                    tags=config["tags"],
                    notes=config["notes"],
                    config=config["config"],
                    mode="online"
                )
                self.initialized = True
                print(f"✅ Wandb monitoring initialized automatically: {self.run.url}")
                print(f"🔑 API key configured and authenticated")
                print(f"📊 Project: {config['project']}")
            except Exception as e:
                print(f"⚠️  Wandb initialization failed: {e}")
                self.initialized = False
        else:
            print("ℹ️  Wandb monitoring disabled - no API key available")
    
    def log_task_metrics(self, task_data: Dict[str, Any]):
        """Log task completion metrics"""
        if not self.initialized:
            return
        
        try:
            wandb.log({
                "task_completed": 1,
                "task_type": task_data.get('task_type'),
                "processing_time": task_data.get('processing_time', 0),
                "accuracy_score": task_data.get('accuracy_score', 0),
                "speed_score": task_data.get('speed_score', 0),
                "miner_count": len(task_data.get('assigned_miners', [])),
                "priority": task_data.get('priority', 'normal')
            })
        except Exception as e:
            print(f"⚠️  Failed to log task metrics: {e}")
    
    def log_miner_performance(self, miner_uid: int, performance_data: Dict[str, Any]):
        """Log individual miner performance"""
        if not self.initialized:
            return
        
        try:
            wandb.log({
                f"miner_{miner_uid}_accuracy": performance_data.get('avg_accuracy_score', 0),
                f"miner_{miner_uid}_speed": performance_data.get('avg_speed_score', 0),
                f"miner_{miner_uid}_processing_time": performance_data.get('avg_processing_time', 0),
                f"miner_{miner_uid}_overall_score": performance_data.get('overall_score', 0),
                f"miner_{miner_uid}_tasks_completed": performance_data.get('completed_tasks', 0)
            })
        except Exception as e:
            print(f"⚠️  Failed to log miner performance: {e}")
    
    def log_system_metrics(self, metrics: Dict[str, Any]):
        """Log system-wide metrics"""
        if not self.initialized:
            return
        
        try:
            wandb.log(metrics)
        except Exception as e:
            print(f"⚠️  Failed to log system metrics: {e}")
    
    def finish(self):
        """Finish the wandb run"""
        if self.initialized and self.run:
            self.run.finish()

# Initialize wandb monitor
wandb_monitor = WandbMonitor(project_name="audio-processing-proxy")

# Initialize FastAPI app
app = FastAPI(
    title="Enhanced Audio Processing Proxy Server",
    description="Advanced proxy server with database integration, workflow orchestration, and real-time monitoring",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests for debugging"""
    start_time = time.time()
    
    # Log the request
    print(f"📥 {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
    
    # Check for problematic requests
    if "None" in str(request.url) or "null" in str(request.url):
        print(f"⚠️  WARNING: Request contains None/null values: {request.url}")
    
    # Process the request
    response = await call_next(request)
    
    # Log response time
    process_time = time.time() - start_time
    print(f"📤 {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
    
    return response

# Add middleware for request tracking
@app.middleware("http")
async def track_requests(request, call_next):
    # Track request
    system_metrics.increment_requests()
    
    # Process request
    response = await call_next(request)
    
    # Track errors
    if response.status_code >= 400:
        system_metrics.increment_errors()
    
    return response

# Global variables for managers
file_manager = None
task_manager = None
workflow_orchestrator = None
validator_api = None
miner_metrics_api = None
leaderboard_api = None
miner_response_handler = None

# Pydantic models for API requests
class TranscriptionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    source_language: str = Field(..., description="Source language code (e.g., 'en', 'es', 'fr')")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="Task priority level")
    callback_url: Optional[str] = Field(None, description="Optional webhook URL for task completion notification")
    
    @validator('source_language')
    def validate_language(cls, v):
        valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi']
        if v.lower() not in valid_languages:
            raise ValueError(f'Language must be one of: {", ".join(valid_languages)}')
        return v.lower()

class TTSRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    text: str = Field(..., description="Text to convert to speech")
    source_language: str = Field(..., description="Source language code (e.g., 'en', 'es', 'fr')")
    priority: TaskPriority = Field(..., description="Task priority level")
    callback_url: Optional[str] = Field(None, description="Optional webhook URL for task completion notification")
    
    @validator('text')
    def validate_text(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        if len(v) > 10000:  # Limit text length
            raise ValueError('Text too long (max 10,000 characters)')
        return v.strip()
    
    @validator('source_language')
    def validate_language(cls, v):
        valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi']
        if v.lower() not in valid_languages:
            raise ValueError(f'Language must be one of: {", ".join(valid_languages)}')
        return v.lower()

class SummarizationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    text: str = Field(..., description="Text to summarize")
    source_language: str = Field(..., description="Source language code (e.g., 'en', 'es', 'fr')")
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, description="Task priority level")
    callback_url: Optional[str] = Field(None, description="Optional webhook URL for task completion notification")
    
    @validator('text')
    def validate_text(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        if len(v) < 50:  # Minimum text length for summarization
            raise ValueError('Text too short for summarization (min 50 characters)')
        if len(v) > 50000:  # Maximum text length
            raise ValueError('Text too long (max 50,000 characters)')
        return v.strip()
    
    @validator('source_language')
    def validate_language(cls, v):
        valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi']
        if v.lower() not in valid_languages:
            raise ValueError(f'Language must be one of: {", ".join(valid_languages)}')
        return v.lower()

# Response models
class TaskResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    task_id: str
    status: TaskStatus
    message: str
    estimated_completion_time: Optional[int] = None
    task_type: str
    source_language: str

class TaskResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    task_id: str
    status: TaskStatus
    task_type: str
    source_language: str
    result: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None
    accuracy_score: Optional[float] = None
    speed_score: Optional[float] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize all managers and start background tasks"""
    global file_manager, task_manager, workflow_orchestrator, validator_api, miner_response_handler, miner_metrics_api
    
    try:
        print("🚀 Starting Enhanced Proxy Server...")
        
        # Initialize PostgreSQL database
        from database.postgresql_adapter import PostgreSQLAdapter
        import os
        
        # Get database URL from environment or use default
        database_url = os.getenv(
            'DATABASE_URL',
            'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
        )
        
        global db_manager
        db_manager = PostgreSQLAdapter(database_url)
        print(f"✅ PostgreSQL database initialized")
        
        # Initialize managers
        global file_manager, task_manager, workflow_orchestrator, validator_api, miner_response_handler, miner_metrics_api
        # Pass PostgreSQL adapter directly (it implements the interface)
        file_manager = FileManager(db_manager)
        task_manager = TaskManager(db_manager)
        # Note: workflow_orchestrator will be initialized after miner_status_manager is created
        validator_api = ValidatorIntegrationAPI(db_manager)
        miner_metrics_api = MinerMetricsAPI(db_manager)  # Now properly declared as global
        global leaderboard_api
        leaderboard_api = LeaderboardAPI(db_manager)
        miner_response_handler = MinerResponseHandler(db_manager, task_manager)
        
        # 🔒 DUPLICATE PROTECTION: Assign components to app.state for endpoint access
        app.state.miner_response_handler = miner_response_handler
        app.state.file_manager = file_manager
        app.state.task_manager = task_manager
        
        # Create and assign task distributor for duplicate protection
        from orchestrators.task_distributor import TaskDistributor
        
        # Create a network-aware miner status manager for the task distributor
        class NetworkMinerStatusManager:
            def __init__(self, db):
                self.db = db
                from database.postgresql_adapter import PostgreSQLAdapter
                # PostgreSQL only - no Firestore support
            
            async def get_available_miners(self, task_type=None, min_count=1, max_count=5):
                """Get available miners from validator reports (simplified - no consensus)"""
                try:
                    # Simplified: Just get miners from MinerStatus table (updated by validators)
                    # No consensus needed - validators already handle that via weight setting
                    from database.postgresql_schema import MinerStatus
                    session = db_manager._get_session()
                    try:
                        miners = session.query(MinerStatus).filter(
                            MinerStatus.is_serving == True
                        ).limit(max_count * 2).all()
                        miner_list = [db_manager._miner_status_to_dict(m) for m in miners]
                    finally:
                        session.close()
                    
                    # Filter by task type if specified
                    if task_type:
                        miner_list = [m for m in miner_list if not m.get('task_type_specialization') or 
                                     task_type in m.get('task_type_specialization', [])]
                    
                    # Filter by capacity
                    available = [m for m in miner_list if 
                                m.get('current_load', 0) < m.get('max_capacity', 5)]
                    
                    # Sort by availability score
                    available.sort(key=lambda x: x.get('availability_score', 0), reverse=True)
                    
                    return available[:max_count]
                    
                except Exception as e:
                    print(f"❌ Error getting network miners: {e}")
                    # Return empty list instead of hardcoded miner - let the system handle no miners gracefully
                    print(f"⚠️  No miners available - returning empty list")
                    return []
            
            def _filter_miners_by_task_type(self, miners, task_type):
                """Filter miners by task type specialization if specified"""
                if not task_type:
                    return miners
                
                filtered = []
                for miner in miners:
                    specialization = miner.get('task_type_specialization')
                    # If miner has no specialization, assume it can handle all tasks
                    if not specialization or task_type in specialization:
                        filtered.append(miner)
                
                return filtered
            
            async def _get_available_miners_simple(self, task_type=None):
                """Get available miners (simplified - no consensus needed)"""
                """Fallback to individual validator reports"""
                try:
                    available_miners = []
                    current_time = datetime.utcnow()
                    
                    # PostgreSQL: Query miner status
                    from database.postgresql_schema import MinerStatus
                    session = self.db._get_session()
                    try:
                        miners = session.query(MinerStatus).filter(
                            MinerStatus.is_serving == True
                        ).all()
                        docs = [self.db._miner_status_to_dict(m) for m in miners]
                    finally:
                        session.close()
                    
                    for doc in docs:
                        miner_data = doc  # Already a dict
                        # Remove stake requirement - allow miners with 0 stake
                        if miner_data.get('is_serving'):
                            # Check last_seen with timezone handling
                            last_seen = miner_data.get('last_seen')
                            if last_seen:
                                try:
                                    # Handle different timestamp formats
                                    if isinstance(last_seen, datetime):
                                        if last_seen.tzinfo is not None:
                                            last_seen = last_seen.replace(tzinfo=None)
                                        time_diff = (current_time - last_seen).total_seconds()
                                    # Handle datetime objects only (PostgreSQL)
                                    # Timestamp is already a datetime object
                                    elif isinstance(last_seen, str):
                                        from dateutil import parser
                                        last_seen_dt = parser.parse(last_seen)
                                        if last_seen_dt.tzinfo:
                                            last_seen_dt = last_seen_dt.replace(tzinfo=None)
                                        time_diff = (current_time - last_seen_dt).total_seconds()
                                    else:
                                        # Unknown format, skip
                                        continue
                                    
                                    # Skip stale miners (not seen in last 15 minutes)
                                    if time_diff >= 900:  # 15 minutes
                                        continue
                                except Exception as e:
                                    print(f"⚠️ Error checking last_seen for miner {miner_data.get('uid', 'unknown')}: {e}")
                                    continue
                            else:
                                # No last_seen, skip this miner
                                continue
                            # Calculate availability score based on performance and stake
                            performance_score = miner_data.get('performance_score', 0.5)
                            stake = float(miner_data.get('stake', 0))
                            current_load = miner_data.get('current_load', 0)
                            max_capacity = miner_data.get('max_capacity', 5)
                            
                            # Calculate availability score (0.0 to 1.0)
                            availability_score = min(1.0, max(0.1, performance_score * (1 - current_load/max_capacity)))
                            
                            available_miners.append({
                                'uid': miner_data['uid'],
                                'hotkey': miner_data.get('hotkey', 'unknown'),
                                'stake': stake,
                                'availability_score': availability_score,
                                'task_type_specialization': miner_data.get('task_type_specialization'),
                                'current_load': current_load,
                                'max_capacity': max_capacity,
                                'performance_score': performance_score,
                                'ip': miner_data.get('ip'),
                                'port': miner_data.get('port'),
                            })
                    
                    # Sort by availability score (higher is better)
                    available_miners.sort(key=lambda x: x['availability_score'], reverse=True)
                    
                    if available_miners:
                        # Only log if miners found (reduce noise)
                        print(f"🔍 Found {len(available_miners)} available miners")
                    
                    return available_miners
                    
                except Exception as e:
                    # Reduce logging noise - only log if it's not a known PostgreSQL issue
                    if "miner_status_collection" not in str(e) and "collection" not in str(e):
                        print(f"⚠️ Error getting fallback miners: {e}")
                    return []
        
        # NOTE: Consensus tracking removed - not needed in proxy server
        # Validators handle consensus via weight setting, proxy just needs miner availability
        
        app.state.miner_status_manager = NetworkMinerStatusManager(db_manager.get_db())
        app.state.task_distributor = TaskDistributor(
            db_manager.get_db(), 
            task_manager, 
            app.state.miner_status_manager
        )
        
        # Initialize workflow orchestrator with miner_status_manager
        workflow_orchestrator = WorkflowOrchestrator(
            db_manager.get_db(), 
            task_manager, 
            app.state.miner_status_manager
        )
        app.state.workflow_orchestrator = workflow_orchestrator  # Make accessible for API endpoints
        
        print("🔒 Duplicate protection components assigned to app.state")
        print("🌐 Network-aware miner status manager initialized")
        
        # Start workflow orchestrator (includes task distribution loop every 5 seconds)
        await workflow_orchestrator.start_orchestration()
        
        # Start TaskDistributor as a backup distribution mechanism (runs every 3 minutes)
        asyncio.create_task(app.state.task_distributor.start_distribution())
        print("✅ TaskDistributor polling started (3 minute interval)")
        
        # Log system startup to wandb
        if wandb_monitor.initialized:
            wandb_monitor.log_system_metrics({
                "system_startup": True,
                "startup_timestamp": datetime.now().isoformat(),
                "server_version": "1.0.0",
                "architecture": "proxy-validator-miner",
                "features": ["caching", "monitoring", "wandb", "grafana"]
            })
            print("📊 Wandb monitoring active - system startup logged")
        
        print("✅ Enhanced Proxy Server started successfully!")
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        raise

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle any unhandled exceptions globally"""
    print(f"❌ Unhandled exception in {request.method} {request.url.path}: {exc}")
    print(f"   Exception type: {type(exc).__name__}")
    print(f"   Client: {request.client.host if request.client else 'unknown'}")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
            "message": "An unexpected error occurred. Please check the server logs."
        }
    )

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    global workflow_orchestrator
    
    try:
        if workflow_orchestrator:
            await workflow_orchestrator.stop_orchestration()
        print("🛑 Enhanced Proxy Server shutdown complete")
    except Exception as e:
        print(f"❌ Error during shutdown: {str(e)}")

# API Endpoints

def get_auth_middleware():
    """Dependency to get auth middleware instance"""
    from middleware.auth_middleware import AuthMiddleware
    return AuthMiddleware(db_manager.get_db())

def require_miner_auth(
    http_request: Request,
    auth_middleware: AuthMiddleware = Depends(get_auth_middleware)
):
    """Dependency to require miner authentication (admin can also access)"""
    api_key = http_request.headers.get("X-API-Key") or http_request.query_params.get("api_key")
    user_info = auth_middleware.verify_api_key(api_key)
    
    # Role is already validated in verify_api_key, but double-check for security
    role = user_info.get('role')
    allowed_roles = {'miner', 'admin'}
    if not role or role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Miner or admin role required")
    
    return user_info

def require_validator_auth(
    http_request: Request,
    auth_middleware: AuthMiddleware = Depends(get_auth_middleware)
):
    """Dependency to require validator authentication (admin can also access)"""
    api_key = http_request.headers.get("X-API-Key") or http_request.query_params.get("api_key")
    user_info = auth_middleware.verify_api_key(api_key)
    
    # Role is already validated in verify_api_key, but double-check for security
    role = user_info.get('role')
    allowed_roles = {'validator', 'admin'}
    if not role or role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Validator or admin role required")
    
    return user_info

def require_client_auth(
    http_request: Request,
    auth_middleware: AuthMiddleware = Depends(get_auth_middleware)
):
    """Dependency to require client authentication (admin can also access)"""
    api_key = http_request.headers.get("X-API-Key") or http_request.query_params.get("api_key")
    user_info = auth_middleware.verify_api_key(api_key)
    
    # Role is already validated in verify_api_key, but double-check for security
    role = user_info.get('role')
    allowed_roles = {'client', 'admin'}
    if not role or role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Client or admin role required")
    
    return user_info

@app.post("/api/v1/transcription")
async def submit_transcription_task(
    audio_file: UploadFile = File(...),
    user_info: dict = Depends(require_client_auth),
    source_language: Optional[str] = Form("en"),
    priority: Optional[str] = Form("normal"),
    model_id: Optional[str] = Form(None)  # Optional HuggingFace model ID
):
    """Submit transcription task with raw audio file (no base64)"""
    try:
        # Ensure form fields are strings
        source_language = source_language or "en"
        priority = priority or "normal"
        model_id = model_id if model_id else None
        
        # Validate file type
        if not audio_file.content_type or not audio_file.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="File must be an audio file")
        
        # Check if R2 storage is enabled
        if not file_manager.r2_storage_manager or not file_manager.r2_storage_manager.enabled:
            raise HTTPException(
                status_code=503,
                detail="R2 Storage is not configured. Please configure R2 credentials in .env file to enable file uploads."
            )
        
        # Read audio file data
        audio_bytes = await audio_file.read()
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        # Create safe filename - handle potential encoding issues
        try:
            filename = audio_file.filename or "audio.wav"
            if isinstance(filename, bytes):
                filename = filename.decode('utf-8', errors='replace')
            safe_filename = create_safe_filename(filename)
        except Exception as e:
            print(f"⚠️ Error processing filename: {e}, using default")
            safe_filename = "audio.wav"
        
        # Upload audio file directly to R2 Storage (raw bytes, no base64)
        try:
            file_id = await file_manager.upload_file(
                file_data=audio_bytes,
                file_name=safe_filename,
                content_type=audio_file.content_type or "audio/wav",
                file_type="audio"
            )
            
            # Get file metadata
            file_metadata = await file_manager.get_file_metadata(file_id)
            
            # Create input_file data with R2 storage info
            # Ensure all values are Firestore-compatible (no binary data)
            public_url = file_metadata.get('public_url') if file_metadata else None
            input_file_data = {
                'file_id': str(file_id),  # Ensure string
                'file_name': str(safe_filename),  # Ensure string
                'file_type': str(audio_file.content_type or 'audio/wav'),  # Ensure string
                'file_size': int(len(audio_bytes)),  # Ensure int
                'uploaded_at': datetime.now(),
                'storage_location': 'r2',
                'public_url': str(public_url) if public_url else None  # Ensure string or None
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload audio file to R2: {str(e)}"
            )
        
        # Create task - ensure all data is Firestore-compatible
        try:
            task_data = {
                'task_type': 'transcription',
                'input_file': input_file_data,
                'priority': str(priority) if priority else 'normal',
                'source_language': str(source_language) if source_language else 'en',
                'model_id': str(model_id) if model_id else "openai/whisper-tiny",  # Default transcription model
                'required_miner_count': 3,
                'min_miner_count': 1,
                'max_miner_count': 3
            }
            
            # Use enhanced database operations
            task_id = DatabaseOperations.create_task(db_manager, task_data)
        except Exception as db_error:
            import traceback
            print(f"❌ Database error: {db_error}")
            print(f"   Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create task in database: {str(db_error)}"
            )
        
        # Auto-assign task to available miners
        assignment_success = DatabaseOperations.auto_assign_task(
            db_manager, 
            task_id, 
            'transcription', 
            task_data.get('required_miner_count', 3),
            min_count=task_data.get('min_miner_count', 1),
            max_count=task_data.get('max_miner_count', task_data.get('required_miner_count', 3))
        )
        
        # Reduce logging - only log successful assignments
        if assignment_success:
            print(f"✅ Task {task_id} assigned to miners")
        # Don't log assignment failures - they're expected when no miners available
        
        # Track metrics
        system_metrics.increment_tasks()
        
        # Log task creation to wandb
        try:
            if wandb_monitor.initialized:
                wandb_monitor.log_task_metrics({
                    'task_type': 'transcription',
                    'task_id': task_id,
                    'priority': priority,
                    'source_language': source_language,
                    'file_size': len(audio_bytes),
                    'created_at': datetime.now().isoformat()
                })
        except Exception as wandb_error:
            print(f"⚠️ Failed to log to wandb: {wandb_error}")
        
        # Start task distribution
        # Note: The workflow orchestrator handles task distribution automatically
        # We don't need to call a specific method here
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Transcription task submitted successfully",
            "auto_assigned": assignment_success
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ Error in submit_transcription_task: {e}")
        print(f"   Traceback: {error_traceback}")
        error_msg = str(e)
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")

@app.post("/api/v1/tts")
async def submit_tts_task(
    text: str = Form(...),
    source_language: str = Form("en"),
    priority: str = Form("normal"),
    model_id: Optional[str] = Form(None),
    voice_name: Optional[str] = Form(None),
    user_info: dict = Depends(require_client_auth)
):
    """Submit text-to-speech task with text stored directly in database - accepts form data"""
    try:
        # All parameters come from form data
        
        # Validate text length
        if not text or len(text.strip()) < 10:
            raise HTTPException(status_code=400, detail="Text too short for TTS (min 10 characters)")
        
        # Validate and get voice information - voice_name is REQUIRED for TTS
        speaker_wav_url = None
        voice_data = None
        
        # If voice_name not provided, try to use a default voice
        if not voice_name:
            # Get the first available voice as default
            from database.postgresql_adapter import PostgreSQLAdapter
            from database.postgresql_schema import Voice
            
            session = db_manager._get_session()
            try:
                default_voice = session.query(Voice).first()
                if default_voice:
                    voice_name = default_voice.voice_name
                    print(f"⚠️ No voice_name provided, using default voice: {voice_name}")
                else:
                    raise HTTPException(
                        status_code=400, 
                        detail="No voice_name provided and no default voice available. Please specify a voice_name or upload a voice first."
                    )
            finally:
                session.close()
        
        # Get voice from database
        if voice_name:
            from database.postgresql_adapter import PostgreSQLAdapter
            from database.postgresql_schema import Voice
            
            # PostgreSQL: Get voice
            session = db_manager._get_session()
            try:
                voice = session.query(Voice).filter(Voice.voice_name == voice_name).first()
                if not voice:
                    raise HTTPException(status_code=404, detail=f"Voice '{voice_name}' not found. Please select a valid voice.")
                speaker_wav_url = voice.public_url
                voice_data = {
                    'voice_name': voice.voice_name,
                    'language': voice.language,
                    'public_url': voice.public_url
                }
            finally:
                session.close()
            
            if not speaker_wav_url:
                raise HTTPException(status_code=404, detail=f"Voice '{voice_name}' has no audio file URL")
            
            # Override language if voice has a specific language
            if voice_data and voice_data.get('language'):
                source_language = voice_data.get('language')
        
        # Use the source language provided by the user
        detected_language = source_language
        language_confidence = 1.0
        
        # Create text content object (don't set content_id - let PostgreSQLAdapter create it)
        text_content = {
            'text': text.strip(),
            'source_language': detected_language,
            'detected_language': detected_language,
            'language_confidence': language_confidence,
            'text_length': len(text),
            'word_count': len(text.split()),
            'metadata': {
                'original_source_language': source_language,
                'detection_method': 'manual'
            }
        }
        
        # Create task data
        task_data = {
            'task_type': 'tts',
            'input_text': text_content,
            'priority': priority,
            'source_language': detected_language,
            'model_id': model_id or "tts_models/multilingual/multi-dataset/xtts_v2",  # Default TTS model
            'voice_name': voice_name,  # Selected voice name
            'speaker_wav_url': speaker_wav_url,  # URL to speaker audio file
            'required_miner_count': 3
        }
        
        # Create task in database
        task_id = DatabaseOperations.create_task(db_manager, task_data)
        
        # Auto-assign task to available miners
        assignment_success = DatabaseOperations.auto_assign_task(
            db_manager,
            task_id,
            'tts',
            task_data.get('required_miner_count', 3),
            min_count=task_data.get('min_miner_count', 1),
            max_count=task_data.get('max_miner_count', task_data.get('required_miner_count', 3))
        )
        
        # Reduce logging - only log successful assignments
        if assignment_success:
            print(f"✅ Task {task_id} assigned to miners")
        # Don't log assignment failures - they're expected when no miners available
        
        # Track metrics
        system_metrics.increment_tasks()
        
        # Log task creation to wandb
        if wandb_monitor.initialized:
            wandb_monitor.log_task_metrics({
                'task_type': 'tts',
                'task_id': task_id,
                'priority': priority,
                'source_language': detected_language,
                'detected_language': detected_language,
                'language_confidence': language_confidence,
                'text_length': len(text),
                'word_count': len(text.split()),
                'created_at': datetime.now().isoformat(),
                'auto_assigned': assignment_success
            })
        
        return {
            "success": True,
            "task_id": task_id,
            "model_id": task_data.get('model_id'),  # Include model_id in response
            "detected_language": detected_language,
            "language_confidence": language_confidence,
            "text_length": len(text),
            "word_count": len(text.split()),
            "auto_assigned": assignment_success,
            "message": "TTS task submitted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")

@app.post("/api/v1/summarization")
async def submit_summarization_task(
    text: str = Form(...),
    source_language: str = Form("en"),
    priority: str = Form("normal"),
    model_id: Optional[str] = Form(None),
    user_info: dict = Depends(require_client_auth)
):
    """Submit summarization task with text stored directly in database - accepts form data"""
    try:
        # All parameters come from form data
        
        # Validate text length
        if not text or len(text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Text too short for summarization (min 50 characters)")
        
        # Use the source language provided by the user
        detected_language = source_language
        language_confidence = 1.0
        
        # Create text content object (don't set content_id - let PostgreSQLAdapter create it)
        text_content = {
            'text': text.strip(),
            'source_language': detected_language,
            'detected_language': detected_language,
            'language_confidence': language_confidence,
            'text_length': len(text),
            'word_count': len(text.split()),
            'metadata': {
                'original_source_language': source_language,
                'detection_method': 'auto' if source_language == "auto" else 'manual'
            }
        }
        
        # Create task using enhanced schema with text content
        task_data = {
            'task_type': 'summarization',
            'input_text': text_content,
            'priority': priority,
            'source_language': detected_language,
            'model_id': model_id or "facebook/bart-large-cnn",  # Default summarization model
            'required_miner_count': 3
        }
        
        # Use enhanced database operations
        task_id = DatabaseOperations.create_task(db_manager, task_data)
        
        # Automatically assign task to available miners
        assignment_success = DatabaseOperations.auto_assign_task(
            db_manager, 
            task_id, 
            'summarization', 
            task_data.get('required_miner_count', 3),
            min_count=task_data.get('min_miner_count', 1),
            max_count=task_data.get('max_miner_count', task_data.get('required_miner_count', 3))
        )
        
        # Reduce logging - only log successful assignments
        if assignment_success:
            print(f"✅ Task {task_id} assigned to miners")
        # Don't log assignment failures - they're expected when no miners available
        
        # Track metrics
        system_metrics.increment_tasks()
        
        # Log task creation to wandb
        if wandb_monitor.initialized:
            wandb_monitor.log_task_metrics({
                'task_type': 'summarization',
                'task_id': task_id,
                'priority': priority,
                'source_language': detected_language,
                'detected_language': detected_language,
                'language_confidence': language_confidence,
                'text_length': len(text),
                'word_count': len(text.split()),
                'created_at': datetime.now().isoformat(),
                'auto_assigned': assignment_success
            })
        
        return {
            "success": True,
            "task_id": task_id,
            "model_id": task_data.get('model_id'),  # Include model_id in response
            "detected_language": detected_language,
            "language_confidence": language_confidence,
            "text_length": len(text),
            "word_count": len(text.split()),
            "auto_assigned": assignment_success,
            "message": "Summarization task submitted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit task: {str(e)}")

@app.post("/api/v1/video-transcription")
async def submit_video_transcription_task(
    video_file: UploadFile = File(...),
    user_info: dict = Depends(require_client_auth),
    source_language: str = Form("en"),
    priority: str = Form("normal"),
    model_id: str = Form(None)  # Optional HuggingFace model ID
):
    """Submit video transcription task - miner will extract audio and transcribe"""
    try:
        # Check if R2 storage is enabled
        if not file_manager.r2_storage_manager or not file_manager.r2_storage_manager.enabled:
            raise HTTPException(
                status_code=503, 
                detail="R2 Storage is not configured. Please configure R2 credentials in .env file to enable file uploads."
            )
        
        # Validate file type - check content_type first, then fallback to file extension
        is_video = False
        if video_file.content_type and video_file.content_type.startswith('video/'):
            is_video = True
        else:
            # Fallback: check file extension
            filename = video_file.filename or ""
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v']
            if any(filename.lower().endswith(ext) for ext in video_extensions):
                is_video = True
        
        if not is_video:
            raise HTTPException(status_code=400, detail="File must be a video file")
        
        # Validate file size (max 100MB for video files)
        file_data = await video_file.read()
        if len(file_data) > 100 * 1024 * 1024:  # 100MB
            raise HTTPException(status_code=400, detail="Video file too large (max 100MB)")
        
        # Create a safe filename for storage
        safe_filename = create_safe_filename(video_file.filename)
        
        # Upload video file to local storage with safe filename
        file_id = await file_manager.upload_file(
            file_data, 
            safe_filename,  # Use safe filename for storage
            video_file.content_type,
            file_type="video_transcription"
        )
        
        # Get the actual file metadata to get the correct path
        file_metadata = await file_manager.get_file_metadata(file_id)
        
        # Determine the correct path based on storage type
        if file_metadata and file_metadata.get('stored_in_cloud', False):
            # File is stored in Firebase Cloud Storage
            file_path = file_metadata.get('cloud_path', f"user_videos/{file_id}")
            storage_location = "cloud_storage"
        else:
            # File is stored in Firestore (small files)
            file_path = f"firestore/{file_id}"
            storage_location = "firestore"
        
        # Create task using enhanced schema
        task_data = {
            'task_type': 'video_transcription',
            'input_file': {
                'file_id': file_id,
                'file_name': video_file.filename,  # Keep original filename for display
                'file_type': video_file.content_type,
                'file_size': len(file_data),
                'local_path': file_path,
                'file_url': f"/api/v1/files/{file_id}",
                'checksum': str(hash(file_data)),  # Simple hash for now
                'uploaded_at': datetime.now(),
                'storage_location': storage_location
            },
            'priority': priority,
            'source_language': source_language,
            'model_id': model_id if model_id else None,  # Store model_id if provided
            'required_miner_count': 3
        }
        
        # Use enhanced database operations
        task_id = DatabaseOperations.create_task(db_manager, task_data)
        
        # Automatically assign task to available miners
        assignment_success = DatabaseOperations.auto_assign_task(
            db_manager, 
            task_id, 
            'video_transcription', 
            task_data.get('required_miner_count', 3),
            min_count=task_data.get('min_miner_count', 1),
            max_count=task_data.get('max_miner_count', task_data.get('required_miner_count', 3))
        )
        
        if assignment_success:
            print(f"✅ Video transcription task {task_id} automatically assigned to miners")
        else:
            print(f"⚠️ Video transcription task {task_id} created but could not be assigned to miners")
        
        # Track metrics
        system_metrics.increment_tasks()
        
        # Log task creation to wandb
        if wandb_monitor.initialized:
            wandb_monitor.log_task_metrics({
                'task_type': 'video_transcription',
                'task_id': task_id,
                'priority': priority,
                'source_language': source_language,
                'file_id': file_id,
                'file_size': len(file_data),
                'created_at': datetime.now().isoformat(),
                'auto_assigned': assignment_success
            })
        
        return {
            "success": True,
            "task_id": task_id,
            "file_id": file_id,
            "file_name": video_file.filename,
            "file_size": len(file_data),
            "source_language": source_language,
            "auto_assigned": assignment_success,
            "message": "Video transcription task submitted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Check if it's a Firebase storage error
        if "403" in error_msg or "storage.googleapis.com" in error_msg or "Firebase" in error_msg or "not configured" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="File storage is not configured. Please configure Firebase credentials to enable file uploads."
            )
        raise HTTPException(status_code=500, detail=f"Failed to submit video transcription task: {str(e)}")

@app.post("/api/v1/text-translation")
async def submit_text_translation_task(
    text: str = Form(...),
    source_language: str = Form(...),
    target_language: str = Form(...),
    priority: str = Form("normal"),
    model_id: Optional[str] = Form(None),
    user_info: dict = Depends(require_client_auth)
):
    """Submit text translation task with text stored directly in database - accepts form data"""
    try:
        # All parameters come from form data
        
        # Validate text length
        if not text or len(text.strip()) < 10:
            raise HTTPException(status_code=400, detail="Text too short for translation (min 10 characters)")
        
        # Validate language codes
        if source_language == target_language:
            raise HTTPException(status_code=400, detail="Source and target languages must be different")
        
        # Create text content object (don't set content_id - let PostgreSQLAdapter create it)
        text_content = {
            'text': text.strip(),
            'source_language': source_language,
            'target_language': target_language,
            'text_length': len(text),
            'word_count': len(text.split()),
            'metadata': {
                'translation_type': 'text',
                'source_language': source_language,
                'target_language': target_language
            }
        }
        
        # Create task data
        task_data = {
            'task_type': 'text_translation',
            'input_text': text_content,
            'priority': priority,
            'source_language': source_language,
            'target_language': target_language,
            'model_id': model_id or "facebook/mbart-large-50-many-to-many-mmt",  # Default translation model
            'required_miner_count': 3
        }
        
        # Create task in database
        task_id = DatabaseOperations.create_task(db_manager, task_data)
        
        # Auto-assign task to available miners
        assignment_success = DatabaseOperations.auto_assign_task(
            db_manager, 
            task_id, 
            'text_translation', 
            task_data.get('required_miner_count', 3),
            min_count=task_data.get('min_miner_count', 1),
            max_count=task_data.get('max_miner_count', task_data.get('required_miner_count', 3))
        )
        
        # Reduce logging - only log successful assignments
        if assignment_success:
            print(f"✅ Task {task_id} assigned to miners")
        # Don't log assignment failures - they're expected when no miners available
        
        # Track metrics
        system_metrics.increment_tasks()
        
        # Log task creation to wandb
        if wandb_monitor.initialized:
            wandb_monitor.log_task_metrics({
                'task_type': 'text_translation',
                'task_id': task_id,
                'priority': priority,
                'source_language': source_language,
                'target_language': target_language,
                'text_length': len(text),
                'word_count': len(text.split()),
                'created_at': datetime.now().isoformat(),
                'auto_assigned': assignment_success
            })
        
        return {
            "success": True,
            "task_id": task_id,
            "model_id": task_data.get('model_id'),  # Include model_id in response
            "source_language": source_language,
            "target_language": target_language,
            "text_length": len(text),
            "word_count": len(text.split()),
            "auto_assigned": assignment_success,
            "message": "Text translation task submitted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit text translation task: {str(e)}")

@app.post("/api/v1/document-translation")
async def submit_document_translation_task(
    user_info: dict = Depends(require_client_auth),
    document_file: UploadFile = File(...),
    source_language: str = Form(...),
    target_language: str = Form(...),
    priority: str = Form("normal"),
    model_id: str = Form(None)  # Optional HuggingFace model ID
):
    """Submit document translation task - miner will extract text and translate"""
    try:
        # Validate file type
        file_extension = document_file.filename.lower().split('.')[-1]
        supported_formats = ['pdf', 'docx', 'txt', 'text']
        
        if file_extension not in supported_formats:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Supported formats: {', '.join(supported_formats)}"
            )
        
        # Validate language codes
        if source_language == target_language:
            raise HTTPException(status_code=400, detail="Source and target languages must be different")
        
        # Validate file size (max 50MB for documents)
        file_data = await document_file.read()
        if len(file_data) > 50 * 1024 * 1024:  # 50MB
            raise HTTPException(status_code=400, detail="Document file too large (max 50MB)")
        
        # Create a safe filename for storage
        safe_filename = create_safe_filename(document_file.filename)
        
        # Upload document file to local storage
        file_id = await file_manager.upload_file(
            file_data, 
            safe_filename,  # Use safe filename for storage
            document_file.content_type,
            file_type="document_translation"
        )
        
        # Get the actual file metadata to get the correct path
        file_metadata = await file_manager.get_file_metadata(file_id)
        
        # Determine the correct path based on storage type
        if file_metadata and file_metadata.get('stored_in_cloud', False):
            # File is stored in Firebase Cloud Storage
            file_path = file_metadata.get('cloud_path', f"user_documents/{file_id}")
            storage_location = "cloud_storage"
        else:
            # File is stored in Firestore (small files)
            file_path = f"firestore/{file_id}"
            storage_location = "firestore"
        
        # Create task using enhanced schema
        task_data = {
            'task_type': 'document_translation',
            'input_file': {
                'file_id': file_id,
                'file_name': document_file.filename,  # Keep original filename for display
                'file_type': document_file.content_type,
                'file_size': len(file_data),
                'local_path': file_path,
                'file_url': f"/api/v1/files/{file_id}",
                'checksum': str(hash(file_data)),  # Simple hash for now
                'uploaded_at': datetime.now(),
                'storage_location': storage_location
            },
            'priority': priority,
            'source_language': source_language,
            'target_language': target_language,
            'model_id': model_id if model_id else None,  # Store model_id if provided
            'required_miner_count': 3
        }
        
        # Use enhanced database operations
        task_id = DatabaseOperations.create_task(db_manager, task_data)
        
        # Automatically assign task to available miners
        assignment_success = DatabaseOperations.auto_assign_task(
            db_manager, 
            task_id, 
            'document_translation', 
            task_data.get('required_miner_count', 3),
            min_count=task_data.get('min_miner_count', 1),
            max_count=task_data.get('max_miner_count', task_data.get('required_miner_count', 3))
        )
        
        # Reduce logging - only log successful assignments
        if assignment_success:
            print(f"✅ Task {task_id} assigned to miners")
        # Don't log assignment failures - they're expected when no miners available
        
        # Track metrics
        system_metrics.increment_tasks()
        
        # Log task creation to wandb
        if wandb_monitor.initialized:
            wandb_monitor.log_task_metrics({
                'task_type': 'document_translation',
                'task_id': task_id,
                'priority': priority,
                'source_language': source_language,
                'target_language': target_language,
                'file_id': file_id,
                'file_size': len(file_data),
                'file_format': file_extension,
                'created_at': datetime.now().isoformat(),
                'auto_assigned': assignment_success
            })
        
        return {
            "success": True,
            "task_id": task_id,
            "model_id": task_data.get('model_id'),  # Include model_id in response
            "file_id": file_id,
            "file_name": document_file.filename,
            "file_size": len(file_data),
            "file_format": file_extension,
            "source_language": source_language,
            "target_language": target_language,
            "auto_assigned": assignment_success,
            "message": "Document translation task submitted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Check if it's a Firebase storage error
        if "403" in error_msg or "storage.googleapis.com" in error_msg or "Firebase" in error_msg or "not configured" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="File storage is not configured. Please configure Firebase credentials to enable file uploads."
            )
        raise HTTPException(status_code=500, detail=f"Failed to submit document translation task: {str(e)}")

@app.get("/api/v1/miner/summarization/{task_id}")
async def get_summarization_task_content(task_id: str):
    """Get summarization task text content for miners"""
    try:
        # Get task from database
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.get('task_type') != 'summarization':
            raise HTTPException(status_code=400, detail="Task is not a summarization task")
        
        # Get text content
        if 'input_text' in task and task['input_text']:
            text_content = task['input_text']
        elif 'input_file' in task and task['input_file']:
            # Fallback to file-based approach
            file_id = task['input_file']['file_id']
            file_content = await file_manager.get_file_content(file_id)
            if file_content:
                text_content = {
                    'text': file_content.decode('utf-8'),
                    'source_language': task.get('source_language', 'en'),
                    'detected_language': task.get('source_language', 'en'),
                    'language_confidence': 1.0
                }
            else:
                raise HTTPException(status_code=404, detail="Text content not found")
        else:
            raise HTTPException(status_code=404, detail="No input content found for task")
        
        return {
            "success": True,
            "task_id": task_id,
            "text_content": text_content,
            "task_metadata": {
                "priority": task.get('priority'),
                "source_language": task.get('source_language', 'en'),
                "required_miner_count": task.get('required_miner_count', 1)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task content: {str(e)}")

@app.get("/api/v1/miner/tts/{task_id}")
async def get_tts_task_content(task_id: str):
    """Get TTS task text content for miners"""
    try:
        # Get task from database
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.get('task_type') != 'tts':
            raise HTTPException(status_code=400, detail="Task is not a TTS task")
        
        # Get text content
        if 'input_text' in task and task['input_text']:
            text_content = task['input_text']
        elif 'input_file' in task and task['input_file']:
            # Fallback to file-based approach
            file_id = task['input_file']['file_id']
            file_content = await file_manager.get_file_content(file_id)
            if file_content:
                text_content = {
                    'text': file_content.decode('utf-8'),
                    'source_language': task.get('source_language', 'en'),
                    'detected_language': task.get('source_language', 'en'),
                    'language_confidence': 1.0
                }
            else:
                raise HTTPException(status_code=404, detail="Text content not found")
        else:
            raise HTTPException(status_code=404, detail="No input content found for task")
        
        # Get voice information for TTS
        voice_info = None
        if task.get('voice_name'):
            voice_info = {
                'voice_name': task.get('voice_name'),
                'speaker_wav_url': task.get('speaker_wav_url'),
                'model_id': task.get('model_id', 'tts_models/multilingual/multi-dataset/xtts_v2')
            }
        
        return {
            "success": True,
            "task_id": task_id,
            "text_content": text_content,
            "voice_info": voice_info,  # Include voice information for TTS
            "task_metadata": {
                "priority": task.get("priority"),
                "source_language": task.get("source_language", "en"),
                "required_miner_count": task.get("required_miner_count", 1),
                "model_id": task.get("model_id", "tts_models/multilingual/multi-dataset/xtts_v2")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task content: {str(e)}")

@app.get("/api/v1/miner/transcription/{task_id}")
async def get_transcription_task_content(task_id: str, request: Request):
    """Get transcription task audio content for miners - returns R2 URL or download URL (no base64)"""
    try:
        # Get task from database
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.get('task_type') != 'transcription':
            raise HTTPException(status_code=400, detail="Task is not a transcription task")
        
        # Get audio file URL from R2 Storage
        if 'input_file' in task and task['input_file']:
            input_file = task['input_file']
            
            # Check for R2 Storage (preferred method - no base64)
            if 'file_id' in input_file and input_file.get('storage_location') == 'r2':
                public_url = input_file.get('public_url')
                if public_url:
                    return {
                        "success": True,
                        "task_id": task_id,
                        "audio_url": public_url,  # Direct R2 URL for download (no base64)
                        "file_metadata": {
                            "file_id": input_file.get('file_id'),
                            "file_name": input_file.get('file_name', 'audio.wav'),
                            "file_type": input_file.get('file_type', 'audio/wav'),
                            "file_size": input_file.get('file_size', 0),
                            "storage_location": "r2"
                        },
                        "task_metadata": {
                            "priority": task.get("priority"),
                            "source_language": task.get("source_language", "en"),
                            "required_miner_count": task.get("required_miner_count", 1)
                        }
                    }
                else:
                    raise HTTPException(status_code=404, detail="R2 public URL not found for audio file")
            
            # Fallback: Handle database-stored files (old storage method)
            elif input_file.get('storage_location') == 'database' or 'file_id' in input_file:
                file_id = input_file.get('file_id')
                if file_id:
                    # Check if it's actually in R2 (might have been migrated)
                    file_metadata = await file_manager.get_file_metadata(file_id)
                    if file_metadata and file_metadata.get('storage_location') == 'r2':
                        public_url = file_metadata.get('public_url')
                        if public_url:
                            return {
                                "success": True,
                                "task_id": task_id,
                                "audio_url": public_url,
                                "file_metadata": {
                                    "file_id": file_id,
                                    "file_name": input_file.get('file_name', 'audio.wav'),
                                    "file_type": input_file.get('file_type', 'audio/wav'),
                                    "file_size": input_file.get('file_size', 0),
                                    "storage_location": "r2"
                                },
                                "task_metadata": {
                                    "priority": task.get("priority"),
                                    "source_language": task.get("source_language", "en"),
                                    "required_miner_count": task.get("required_miner_count", 1)
                                }
                            }
                    
                    # Fallback: Provide download URL for database-stored files
                    base_url = str(request.base_url).rstrip('/')
                    download_url = f"{base_url}/api/v1/files/{file_id}/download"
                    return {
                        "success": True,
                        "task_id": task_id,
                        "audio_url": download_url,  # Download URL for database-stored files
                        "file_metadata": {
                            "file_id": file_id,
                            "file_name": input_file.get('file_name', 'audio.wav'),
                            "file_type": input_file.get('file_type', 'audio/wav'),
                            "file_size": input_file.get('file_size', 0),
                            "storage_location": input_file.get('storage_location', 'database')
                        },
                        "task_metadata": {
                            "priority": task.get("priority"),
                            "source_language": task.get("source_language", "en"),
                            "required_miner_count": task.get("required_miner_count", 1)
                        }
                    }
                else:
                    raise HTTPException(status_code=404, detail="No file_id found in task input_file")
            else:
                raise HTTPException(status_code=404, detail="No valid audio file found in task (neither R2 nor database storage)")
        else:
            raise HTTPException(status_code=404, detail="No input file found for transcription task")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transcription task content: {str(e)}")

@app.get("/api/v1/miner/video-transcription/{task_id}")
async def get_video_transcription_task_content(task_id: str):
    """Get video transcription task file content for miners"""
    try:
        # Get task from database
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.get('task_type') != 'video_transcription':
            raise HTTPException(status_code=400, detail="Task is not a video transcription task")
        
        # Get file metadata (miners will download from R2 URL themselves)
        if 'input_file' in task and task['input_file']:
            file_metadata = task['input_file']
            # Ensure we have a download URL
            if not file_metadata.get('public_url') and file_metadata.get('file_id'):
                # Get file metadata from database to get R2 URL
                file_info = await file_manager.get_file_metadata(file_metadata['file_id'])
                if file_info and file_info.get('public_url'):
                    file_metadata['public_url'] = file_info['public_url']
                    file_metadata['r2_key'] = file_info.get('r2_key')
            
            return {
                "success": True,
                "task_id": task_id,
                "file_metadata": file_metadata,
                "download_url": file_metadata.get('public_url') or f"/api/v1/files/{file_metadata.get('file_id')}",
                "task_metadata": {
                    "priority": task.get("priority"),
                    "source_language": task.get("source_language", "en"),
                    "required_miner_count": task.get("required_miner_count", 1)
                }
            }
        else:
            raise HTTPException(status_code=404, detail="No input file found for video transcription task")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get video transcription task content: {str(e)}")

@app.get("/api/v1/miner/text-translation/{task_id}")
async def get_text_translation_task_content(task_id: str):
    """Get text translation task text content for miners"""
    try:
        # Get task from database
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.get('task_type') != 'text_translation':
            raise HTTPException(status_code=400, detail="Task is not a text translation task")
        
        # Get text content
        if 'input_text' in task and task['input_text']:
            text_content = task['input_text']
        else:
            raise HTTPException(status_code=404, detail="No input text found for text translation task")
        
        return {
            "success": True,
            "task_id": task_id,
            "text_content": text_content,
            "task_metadata": {
                "priority": task.get("priority"),
                "source_language": task.get("source_language", "en"),
                "target_language": task.get("target_language", "es"),
                "required_miner_count": task.get("required_miner_count", 1)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get text translation task content: {str(e)}")

@app.get("/api/v1/miner/document-translation/{task_id}")
async def get_document_translation_task_content(task_id: str):
    """Get document translation task file content for miners"""
    try:
        # Get task from database
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.get('task_type') != 'document_translation':
            raise HTTPException(status_code=400, detail="Task is not a document translation task")
        
        # Get file content
        if 'input_file' in task and task['input_file']:
            file_id = task['input_file']['file_id']
            file_content = await file_manager.get_file_content(file_id)
            if file_content:
                return {
                    "success": True,
                    "task_id": task_id,
                    "file_content": file_content,
                    "file_metadata": task['input_file'],
                    "task_metadata": {
                        "priority": task.get("priority"),
                        "source_language": task.get("source_language", "en"),
                        "target_language": task.get("target_language", "es"),
                        "required_miner_count": task.get("required_miner_count", 1)
                    }
                }
            else:
                raise HTTPException(status_code=404, detail="Document file content not found")
        else:
            raise HTTPException(status_code=404, detail="No input file found for document translation task")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get document translation task content: {str(e)}")

@app.post("/api/v1/miner/tts/upload-audio")
async def upload_tts_audio(
    task_id: str = Form(...),
    miner_uid: int = Form(...),
    audio_file: UploadFile = File(...),
    processing_time: float = Form(0.0),  # Made optional with default
    accuracy_score: float = Form(0.0),
    speed_score: float = Form(0.0)
):
    """Upload TTS audio file generated by miner"""
    try:
        # Validate required parameters
        if not task_id or task_id == "None" or task_id == "null":
            raise HTTPException(status_code=400, detail="Invalid task_id provided")
        
        if not miner_uid or miner_uid <= 0:
            raise HTTPException(status_code=400, detail="Invalid miner_uid provided")
        
        # Validate audio file
        if not audio_file.filename or not audio_file.filename.endswith('.wav'):
            raise HTTPException(status_code=400, detail="Audio file must be a .wav file")
        
        # Read audio file content
        audio_content = await audio_file.read()
        if len(audio_content) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        # Generate unique filename
        import uuid
        audio_filename = f"{task_id}_{miner_uid}_{uuid.uuid4().hex[:8]}.wav"
        
        # Store audio file in Firebase Cloud Storage
        file_id = await file_manager.upload_file(
            audio_content,
            audio_filename,
            "audio/wav",
            file_type="tts"
        )
        
        # Get file metadata
        file_metadata = await file_manager.get_file_metadata(file_id)
        
        # Create file reference
        file_reference = {
            'file_id': file_id,
            'file_name': audio_filename,
            'file_type': 'audio/wav',
            'file_size': len(audio_content),
            'local_path': file_metadata.get('cloud_path', f"tts_audio/{file_id}") if file_metadata else f"tts_audio/{file_id}",
            'file_url': f"/api/v1/tts/audio/{file_id}",
            'checksum': str(hash(audio_content)),
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'storage_location': 'cloud_storage'
        }
        
        # Create response data with audio file info
        response_data = {
            'output_data': {
                'audio_file': file_reference,
                'audio_duration': 0.0,  # Will be calculated by validator
                'sample_rate': 22050,   # Default, will be verified by validator
                'bit_depth': 16,        # Default, will be verified by validator
                'channels': 1           # Default, will be verified by validator
            },
            'processing_time': processing_time,
            'accuracy_score': accuracy_score,
            'speed_score': speed_score
        }
        
        # Submit the response
        success = await miner_response_handler.handle_miner_response(task_id, miner_uid, response_data)
        
        if success:
            print(f"✅ TTS audio uploaded successfully for task {task_id} by miner {miner_uid}")
            print(f"   Audio file: {audio_filename}")
            print(f"   File size: {len(audio_content)} bytes")
            print(f"   File ID: {file_id}")
            
            return {
                "success": True,
                "message": "TTS audio uploaded successfully",
                "task_id": task_id,
                "miner_uid": miner_uid,
                "audio_file": file_reference,
                "file_url": f"/api/v1/tts/audio/{file_id}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to process TTS response")
            
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error uploading TTS audio: {e}")
        # Check if it's a Firebase storage error
        if "403" in error_msg or "storage.googleapis.com" in error_msg or "Firebase" in error_msg or "not configured" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="File storage is not configured. Please configure Firebase credentials to enable file uploads."
            )
        raise HTTPException(status_code=500, detail=f"Failed to upload audio: {str(e)}")

@app.get("/api/v1/tts/audio/{file_id}")
async def get_tts_audio(file_id: str):
    """Serve TTS audio files from R2 Storage or public URL"""
    try:
        # Get file metadata first to check for public URL
        file_metadata = await file_manager.get_file_metadata(file_id)
        if not file_metadata:
            raise HTTPException(status_code=404, detail="Audio file metadata not found")
        
        # Get file from R2 Storage or use public URL if available
        file_content = await file_manager.download_file(file_id)
        if not file_content:
            # If download fails but we have a public URL, return redirect
            if file_metadata.get('public_url'):
                from fastapi.responses import RedirectResponse
                return RedirectResponse(url=file_metadata['public_url'], status_code=302)
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        filename = file_metadata.get('original_filename') or file_metadata.get('file_name', f"{file_id}.wav")
        
        # Handle Unicode filenames properly
        safe_filename = urllib.parse.quote(filename)
        
        # Return audio file as streaming response
        return StreamingResponse(
            iter([file_content]),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error serving TTS audio: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to serve audio: {str(e)}")

@app.post("/api/v1/miner/video-transcription/upload-result")
async def upload_video_transcription_result(
    task_id: str = Form(...),
    miner_uid: int = Form(...),
    transcript: str = Form(...),
    processing_time: float = Form(0.0),
    accuracy_score: float = Form(0.0),
    speed_score: float = Form(0.0),
    confidence: float = Form(0.0),
    language: str = Form("en")
):
    """Upload video transcription result from miner - accepts form data"""
    try:
        # All parameters come from form data
        
        # Validate required parameters
        if not task_id or task_id == "None" or task_id == "null":
            raise HTTPException(status_code=400, detail="Invalid task_id provided")
        
        if not miner_uid or miner_uid <= 0:
            raise HTTPException(status_code=400, detail="Invalid miner_uid provided")
        
        if not transcript or transcript.strip() == "":
            raise HTTPException(status_code=400, detail="Transcript cannot be empty")
        
        # Create response data
        response_data = {
            'output_data': {
                'transcript': transcript.strip(),
                'confidence': confidence,
                'processing_time': processing_time,
                'language': language
            },
            'processing_time': processing_time,
            'accuracy_score': accuracy_score,
            'speed_score': speed_score
        }
        
        # Log the response submission for debugging
        print(f"📥 Miner {miner_uid} submitting video transcription result for task {task_id}")
        print(f"   Transcript length: {len(transcript)} characters")
        print(f"   Processing time: {processing_time}s")
        print(f"   Confidence: {confidence}")
        print(f"   Language: {language}")
        
        # Check if task exists first
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Handle the response with miner_response_handler
        success = await miner_response_handler.handle_miner_response(task_id, miner_uid, response_data)
        
        if success:
            print(f"✅ Video transcription result uploaded successfully for task {task_id} by miner {miner_uid}")
            return {
                "success": True,
                "message": "Video transcription result uploaded successfully",
                "task_id": task_id,
                "miner_uid": miner_uid,
                "transcript_length": len(transcript),
                "confidence": confidence,
                "language": language
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to process video transcription response (task may not exist or duplicate response)")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error uploading video transcription result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload result: {str(e)}")

@app.post("/api/v1/miner/text-translation/upload-result")
async def upload_text_translation_result(
    task_id: str = Form(...),
    miner_uid: int = Form(...),
    translated_text: str = Form(...),
    processing_time: float = Form(0.0),
    accuracy_score: float = Form(0.0),
    speed_score: float = Form(0.0),
    source_language: str = Form(""),
    target_language: str = Form("")
):
    """Upload text translation result from miner - accepts form data"""
    try:
        # All parameters come from form data
        
        # Validate required parameters
        if not task_id or task_id == "None" or task_id == "null":
            raise HTTPException(status_code=400, detail="Invalid task_id provided")
        
        if not miner_uid or miner_uid <= 0:
            raise HTTPException(status_code=400, detail="Invalid miner_uid provided")
        
        if not translated_text or translated_text.strip() == "":
            raise HTTPException(status_code=400, detail="Translated text cannot be empty")
        
        # Create response data
        response_data = {
            'output_data': {
                'translated_text': translated_text.strip(),
                'source_language': source_language,
                'target_language': target_language,
                'processing_time': processing_time
            },
            'processing_time': processing_time,
            'accuracy_score': accuracy_score,
            'speed_score': speed_score
        }
        
        # Check if task exists first
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Log the response submission for debugging
        print(f"📥 Miner {miner_uid} submitting text translation result for task {task_id}")
        print(f"   Translated text length: {len(translated_text)} characters")
        print(f"   Processing time: {processing_time}s")
        print(f"   From {source_language} to {target_language}")
        
        # Handle the response with miner_response_handler
        success = await miner_response_handler.handle_miner_response(task_id, miner_uid, response_data)
        
        if success:
            print(f"✅ Text translation result uploaded successfully for task {task_id} by miner {miner_uid}")
            return {
                "success": True,
                "message": "Text translation result uploaded successfully",
                "task_id": task_id,
                "miner_uid": miner_uid,
                "translated_text_length": len(translated_text),
                "source_language": source_language,
                "target_language": target_language
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to process text translation response")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error uploading text translation result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload result: {str(e)}")

@app.post("/api/v1/miner/document-translation/upload-result")
async def upload_document_translation_result(
    task_id: str = Form(...),
    miner_uid: int = Form(...),
    translated_text: str = Form(...),
    processing_time: float = Form(0.0),
    accuracy_score: float = Form(0.0),
    speed_score: float = Form(0.0),
    source_language: str = Form(""),
    target_language: str = Form(""),
    metadata: str = Form("{}")
):
    """Upload document translation result from miner - accepts form data"""
    try:
        # All parameters come from form data
        
        # Validate required parameters
        if not task_id or task_id == "None" or task_id == "null":
            raise HTTPException(status_code=400, detail="Invalid task_id provided")
        
        if not miner_uid or miner_uid <= 0:
            raise HTTPException(status_code=400, detail="Invalid miner_uid provided")
        
        if not translated_text or translated_text.strip() == "":
            raise HTTPException(status_code=400, detail="Translated text cannot be empty")
        
        # Parse metadata if provided
        import json
        try:
            metadata_dict = json.loads(metadata) if metadata else {}
        except json.JSONDecodeError:
            metadata_dict = {}
        
        # Create response data
        response_data = {
            'output_data': {
                'translated_text': translated_text.strip(),
                'source_language': source_language,
                'target_language': target_language,
                'processing_time': processing_time,
                'metadata': metadata_dict
            },
            'processing_time': processing_time,
            'accuracy_score': accuracy_score,
            'speed_score': speed_score
        }
        
        # Check if task exists first
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Log the response submission for debugging
        print(f"📥 Miner {miner_uid} submitting document translation result for task {task_id}")
        print(f"   Translated text length: {len(translated_text)} characters")
        print(f"   Processing time: {processing_time}s")
        print(f"   From {source_language} to {target_language}")
        
        # Handle the response with miner_response_handler
        success = await miner_response_handler.handle_miner_response(task_id, miner_uid, response_data)
        
        if success:
            print(f"✅ Document translation result uploaded successfully for task {task_id} by miner {miner_uid}")
            return {
                "success": True,
                "message": "Document translation result uploaded successfully",
                "task_id": task_id,
                "miner_uid": miner_uid,
                "translated_text_length": len(translated_text),
                "source_language": source_language,
                "target_language": target_language,
                "metadata": metadata_dict
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to process document translation response")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error uploading document translation result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload result: {str(e)}")

def get_auth_middleware():
    """Dependency to get auth middleware instance"""
    from middleware.auth_middleware import AuthMiddleware
    return AuthMiddleware(db_manager.get_db())

def require_miner_auth(
    http_request: Request,
    auth_middleware: AuthMiddleware = Depends(get_auth_middleware)
):
    """Dependency to require miner authentication (admin can also access)"""
    api_key = http_request.headers.get("X-API-Key") or http_request.query_params.get("api_key")
    user_info = auth_middleware.verify_api_key(api_key)
    
    # Role is already validated in verify_api_key, but double-check for security
    role = user_info.get('role')
    allowed_roles = {'miner', 'admin'}
    if not role or role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Miner or admin role required")
    
    return user_info

def require_validator_auth(
    http_request: Request,
    auth_middleware: AuthMiddleware = Depends(get_auth_middleware)
):
    """Dependency to require validator authentication (admin can also access)"""
    api_key = http_request.headers.get("X-API-Key") or http_request.query_params.get("api_key")
    user_info = auth_middleware.verify_api_key(api_key)
    
    # Role is already validated in verify_api_key, but double-check for security
    role = user_info.get('role')
    allowed_roles = {'validator', 'admin'}
    if not role or role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Validator or admin role required")
    
    return user_info

def require_client_auth(
    http_request: Request,
    auth_middleware: AuthMiddleware = Depends(get_auth_middleware)
):
    """Dependency to require client authentication (admin can also access)"""
    api_key = http_request.headers.get("X-API-Key") or http_request.query_params.get("api_key")
    user_info = auth_middleware.verify_api_key(api_key)
    
    # Role is already validated in verify_api_key, but double-check for security
    role = user_info.get('role')
    allowed_roles = {'client', 'admin'}
    if not role or role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Client or admin role required")
    
    return user_info

@app.post("/api/v1/miner/response")
async def submit_miner_response(
    task_id: str = Form(...),
    miner_uid: int = Form(...),
    response_data: str = Form(...),
    processing_time: float = Form(0.0),
    accuracy_score: float = Form(0.0),
    speed_score: float = Form(0.0),
    hotkey: Optional[str] = Form(None),
    coldkey_address: Optional[str] = Form(None),
    network: Optional[str] = Form(None),
    user_info: dict = Depends(require_miner_auth)
):
    """Submit miner response for a task - accepts form data"""
    try:
        # All parameters come from form data
        
        # Validate required parameters
        if not task_id or task_id == "None" or task_id == "null":
            raise HTTPException(status_code=400, detail="Invalid task_id provided")
        
        if not miner_uid or miner_uid <= 0:
            raise HTTPException(status_code=400, detail="Invalid miner_uid provided")
        
        # Extract miner credentials from form (for validation)
        miner_hotkey = hotkey
        miner_coldkey = coldkey_address
        miner_network = network
        
        # If credentials provided, verify they match the API key
        if miner_hotkey and miner_coldkey and miner_network:
            from middleware.auth_middleware import AuthMiddleware
            auth_middleware = AuthMiddleware(db_manager.get_db())
            if not auth_middleware.verify_miner_credentials(
                user_info,
                miner_hotkey,
                miner_coldkey,
                miner_uid,
                miner_network
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Miner credentials do not match the provided API key"
                )
        
        # Parse response data (assuming it's JSON string)
        import json
        try:
            response_data_dict = json.loads(response_data)
        except json.JSONDecodeError:
            response_data_dict = {"output_data": response_data}
        
        # Validate response data structure
        if not response_data_dict:
            raise HTTPException(status_code=400, detail="Empty response data provided")
        
        # Create response payload
        response_payload = {
            'output_data': response_data_dict,
            'processing_time': processing_time,
            'accuracy_score': accuracy_score,
            'speed_score': speed_score
        }
        
        # Check if task exists first
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Log the response submission for debugging
        print(f"📥 Miner {miner_uid} submitting response for task {task_id}")
        print(f"   Processing time: {processing_time}s")
        print(f"   Accuracy score: {accuracy_score}")
        print(f"   Speed score: {speed_score}")
        
        # Handle the response directly with miner_response_handler
        success = await miner_response_handler.handle_miner_response(task_id, miner_uid, response_payload)
        
        if success:
            # Track metrics
            system_metrics.increment_miner_responses()
            
            # Log metrics to wandb
            wandb_monitor.log_task_metrics({
                'task_type': 'miner_response',
                'processing_time': processing_time,
                'accuracy_score': accuracy_score,
                'speed_score': speed_score,
                'miner_uid': miner_uid
            })
            
            # Invalidate cache for this task
            cache.invalidate(f"task_status_{task_id}")
            
            print(f"✅ Miner response for task {task_id} processed successfully")
            
            return {
                "success": True,
                "message": "Miner response submitted successfully",
                "task_id": task_id,
                "miner_uid": miner_uid
            }
        else:
            print(f"❌ Failed to process miner response for task {task_id}")
            raise HTTPException(status_code=400, detail="Failed to process miner response (task may not exist or duplicate response)")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Unexpected error in submit_miner_response: {e}")
        print(f"   Task ID: {task_id}")
        print(f"   Miner UID: {miner_uid}")
        raise HTTPException(status_code=500, detail=f"Failed to submit response: {str(e)}")

@app.post("/api/v1/miner/tts/upload")
async def upload_tts_audio(
    task_id: str = Form(...),
    miner_uid: int = Form(...),
    audio_file: UploadFile = File(...),
    processing_time: float = Form(0.0),  # Made optional with default
    accuracy_score: float = Form(0.0),
    speed_score: float = Form(0.0),
    user_info: dict = Depends(require_miner_auth)
):
    """Upload TTS audio file from miner"""
    try:
        # Validate required parameters
        if not task_id or task_id == "None" or task_id == "null":
            raise HTTPException(status_code=400, detail="Invalid task_id provided")
        
        if not miner_uid or miner_uid <= 0:
            raise HTTPException(status_code=400, detail="Invalid miner_uid provided")
        
        # Validate audio file
        if not audio_file or audio_file.filename == "":
            raise HTTPException(status_code=400, detail="No audio file provided")
        
        # Check file type (should be .wav)
        if not audio_file.filename.lower().endswith('.wav'):
            raise HTTPException(status_code=400, detail="Audio file must be .wav format")
        
        # Read audio file content
        audio_content = await audio_file.read()
        if len(audio_content) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{task_id}_{miner_uid}_{timestamp}.wav"
        
        # Store audio file in Firebase Cloud Storage
        file_id = await file_manager.upload_file(
            audio_content,
            filename,
            "audio/wav",
            file_type="tts"
        )
        
        # Get file metadata
        file_metadata = await file_manager.get_file_metadata(file_id)
        
        # Create file reference
        file_reference = {
            'file_id': file_id,
            'file_name': filename,
            'file_type': "audio/wav",
            'file_size': len(audio_content),
            'local_path': file_metadata.get('cloud_path', f"tts_audio/{file_id}") if file_metadata else f"tts_audio/{file_id}",
            'file_url': f"/api/v1/tts/audio/{file_id}",
            'checksum': str(hash(audio_content)),
            'created_at': datetime.now(),
            'storage_location': 'cloud_storage'
        }
        
        # Create response payload
        response_payload = {
            'output_data': {
                'audio_file': file_reference,
                'duration': 0.0,  # Will be calculated by validator
                'sample_rate': 22050,  # Default sample rate
                'format': 'wav'
            },
            'processing_time': processing_time,
            'accuracy_score': accuracy_score,
            'speed_score': speed_score
        }
        
        # Handle the response with miner_response_handler
        success = await miner_response_handler.handle_miner_response(task_id, miner_uid, response_payload)
        
        if success:
            print(f"✅ TTS audio uploaded successfully for task {task_id} by miner {miner_uid}")
            print(f"   File: {filename}")
            print(f"   Size: {len(audio_content)} bytes")
            print(f"   File ID: {file_id}")
            
            return {
                "success": True,
                "message": "TTS audio uploaded successfully",
                "task_id": task_id,
                "miner_uid": miner_uid,
                "audio_file": file_reference,
                "file_url": f"/api/v1/tts/audio/{file_id}"
            }
        else:
            print(f"❌ Failed to process TTS audio upload for task {task_id}")
            raise HTTPException(status_code=500, detail="Failed to process TTS audio upload")
            
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Unexpected error in upload_tts_audio: {e}")
        # Check if it's a Firebase storage error
        if "403" in error_msg or "storage.googleapis.com" in error_msg or "Firebase" in error_msg or "not configured" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="File storage is not configured. Please configure Firebase credentials to enable file uploads."
            )
        raise HTTPException(status_code=500, detail=f"Failed to upload TTS audio: {str(e)}")

@app.get("/api/v1/validator/tasks")
async def get_tasks_for_validator(
    validator_uid: int = None,
    user_info: dict = Depends(require_validator_auth)
):
    """Get tasks ready for validator evaluation"""
    try:
        print(f"🔍 Validator requesting tasks (validator_uid: {validator_uid})")
        
        # If no validator_uid provided, get all tasks ready for evaluation
        if validator_uid is None:
            tasks = await validator_api.get_tasks_for_evaluation()
        else:
            tasks = await validator_api.get_tasks_for_evaluation(validator_uid)
        
        print(f"✅ Retrieved {len(tasks)} tasks for validator")
        
        # Debug: Log task structure for first few tasks
        for i, task in enumerate(tasks[:3]):  # Log first 3 tasks
            print(f"   Task {i+1}: {task.get('task_id', 'no_id')}")
            print(f"      Type: {task.get('task_type', 'no_type')}")
            print(f"      Status: {task.get('status', 'no_status')}")
            print(f"      Has input_data: {'input_data' in task}")
            print(f"      Has input_file: {'input_file' in task}")
            print(f"      Has input_file_id: {'input_file_id' in task}")
            if 'input_data' in task and task['input_data']:
                print(f"      Input data type: {type(task['input_data']).__name__}")
                if isinstance(task['input_data'], str):
                    print(f"      Input data length: {len(task['input_data'])} chars")
                elif isinstance(task['input_data'], bytes):
                    print(f"      Input data length: {len(task['input_data'])} bytes")
            print()
        
        return {
            "success": True,
            "tasks": tasks,
            "count": len(tasks)
        }
        
    except Exception as e:
        print(f"❌ Error in get_tasks_for_validator: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get tasks: {str(e)}")

@app.get("/api/v1/miners/{miner_uid}/metrics")
async def get_miner_metrics_endpoint(
    miner_uid: int,
    hotkey: str = None,
    user_info: dict = Depends(require_validator_auth)
):
    """
    Get centralized miner metrics for a specific miner.
    This is the SINGLE SOURCE OF TRUTH for all validators.
    All validators should use this endpoint to get the same metrics.
    """
    try:
        if not miner_metrics_api:
            raise HTTPException(status_code=500, detail="Miner metrics API not initialized")
        
        metrics = await miner_metrics_api.get_miner_metrics(miner_uid, hotkey)
        
        if not metrics:
            return {
                "success": False,
                "message": f"No metrics found for miner {miner_uid}",
                "metrics": None
            }
        
        return {
            "success": True,
            "metrics": metrics
        }
    except Exception as e:
        print(f"❌ Error getting miner metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get miner metrics: {str(e)}")

@app.get("/api/v1/miners/metrics/all")
async def get_all_miner_metrics_endpoint(
    user_info: dict = Depends(require_validator_auth)
):
    """
    Get metrics for all miners.
    This allows validators to fetch all metrics at once for reward calculation.
    """
    try:
        if not miner_metrics_api:
            raise HTTPException(status_code=500, detail="Miner metrics API not initialized")
        
        all_metrics = await miner_metrics_api.get_all_miner_metrics()
        
        return {
            "success": True,
            "count": len(all_metrics),
            "metrics": all_metrics
        }
    except Exception as e:
        print(f"❌ Error getting all miner metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get all miner metrics: {str(e)}")

@app.post("/api/v1/validators/mark-task-seen")
async def mark_task_as_seen_by_validator(
    task_id: str = Form(...),
    validator_uid: int = Form(...),
    validator_identifier: str = Form(...),
    evaluated_at: str = Form(...),
    user_info: dict = Depends(require_validator_auth)
):
    """Mark a task as seen/evaluated by a validator to prevent duplicate rewards"""
    try:
        from database.postgresql_adapter import PostgreSQLAdapter
        db = db_manager.get_db()
        
        if not isinstance(db, PostgreSQLAdapter):
            raise HTTPException(status_code=500, detail="Database adapter not supported")
        
        # Get current task
        task = db.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Get current validators_seen list
        validators_seen = task.get('validators_seen', [])
        validators_seen_timestamps = task.get('validators_seen_timestamps', {})
        
        # Add validator if not already present
        if validator_identifier not in validators_seen:
            validators_seen.append(validator_identifier)
            validators_seen_timestamps[validator_identifier] = evaluated_at
            
            # Update task in database
            db.update_task(task_id, {
                'validators_seen': validators_seen,
                'validators_seen_timestamps': validators_seen_timestamps
            })
            
            print(f"✅ Task {task_id} marked as seen by validator {validator_identifier}")
            return {
                "success": True,
                "message": f"Task {task_id} marked as seen by validator {validator_identifier}",
                "validators_seen": validators_seen
            }
        else:
            print(f"ℹ️  Task {task_id} already seen by validator {validator_identifier}")
            return {
                "success": True,
                "message": f"Task {task_id} already seen by validator {validator_identifier}",
                "validators_seen": validators_seen
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error marking task as seen: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark task as seen: {str(e)}")

@app.get("/api/v1/validator/{validator_uid}/evaluated_tasks")
async def get_validator_evaluated_tasks(
    validator_uid: int,
    validator_identifier: str = None,
    user_info: dict = Depends(require_validator_auth)
):
    """Get list of task IDs that have been evaluated by a specific validator"""
    try:
        from database.postgresql_adapter import PostgreSQLAdapter
        from database.postgresql_schema import Task
        from sqlalchemy import text
        
        db = db_manager.get_db()
        
        if not isinstance(db, PostgreSQLAdapter):
            raise HTTPException(status_code=500, detail="Database adapter not supported")
        
        # If validator_identifier is not provided, construct it to match validator's format
        # The validator uses "validator_{uid}" format when marking tasks
        if validator_identifier is None:
            # Try to get from user_info if available (hotkey)
            hotkey = user_info.get('hotkey') if user_info else None
            if hotkey:
                # Validator might use hotkey-based identifier in some cases
                validator_identifier = f"validator_{hotkey}"
            else:
                # Default: use UID-based identifier (matches validator's mark_task_as_validator_evaluated)
                validator_identifier = f"validator_{validator_uid}"
        
        print(f"🔍 Getting evaluated tasks for validator {validator_uid} (identifier: {validator_identifier})")
        
        # Query tasks where this validator is in validators_seen
        session = db._get_session()
        try:
            # Use SQLAlchemy's native JSONB operators for efficient querying
            from sqlalchemy import or_, cast
            from sqlalchemy.dialects.postgresql import JSONB
            
            # Create JSONB arrays for the contains operator (@>)
            # The @> operator checks if the left JSONB value contains the right JSONB value
            validator_array = [validator_identifier]
            uid_array = [str(validator_uid)]
            
            # Use native SQLAlchemy JSONB operators - no raw SQL needed
            query = session.query(Task.task_id).filter(
                or_(
                    Task.validators_seen.op('@>')(cast(validator_array, JSONB)),
                    Task.validators_seen.op('@>')(cast(uid_array, JSONB))
                )
            )
            
            task_ids = [str(task_id) for task_id, in query.all()]
            
            print(f"✅ Found {len(task_ids)} evaluated tasks for validator {validator_uid}")
            
            return {
                "success": True,
                "evaluated_tasks": task_ids,
                "count": len(task_ids)
            }
        finally:
            session.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting evaluated tasks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get evaluated tasks: {str(e)}")

@app.post("/api/v1/validator/evaluation")
async def submit_validator_evaluation(
    task_id: str = Form(...),
    validator_uid: int = Form(...),
    evaluation_data: str = Form("{}"),
    hotkey: Optional[str] = Form(None),
    coldkey_address: Optional[str] = Form(None),
    network: Optional[str] = Form(None),
    user_info: dict = Depends(require_validator_auth)
):
    """Submit validator evaluation and rewards - accepts form data"""
    try:
        # All parameters come from form data
        import json
        # Parse evaluation JSON
        evaluation_dict = json.loads(evaluation_data)
        
        # Extract validator credentials from form (for validation)
        validator_hotkey = hotkey
        validator_coldkey = coldkey_address
        validator_network = network
        
        # If credentials provided, verify they match the API key
        if validator_hotkey and validator_coldkey and validator_network:
            from middleware.auth_middleware import AuthMiddleware
            auth_middleware = AuthMiddleware(db_manager.get_db())
            if not auth_middleware.verify_validator_credentials(
                user_info,
                validator_hotkey,
                validator_coldkey,
                validator_uid,
                validator_network
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Validator credentials do not match the provided API key"
                )
        
        # Submit evaluation
        try:
            await validator_api.submit_validator_evaluation(task_id, validator_uid, evaluation_dict)
        except ValueError as e:
            # ValueError from validator_integration means task not found
            if "not found" in str(e).lower():
                raise HTTPException(status_code=404, detail=f"Task not found")
            raise
        
        return {"success": True, "message": "Evaluation submitted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Check if task not found
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=f"Task not found")
        raise HTTPException(status_code=500, detail=f"Failed to submit evaluation: {str(e)}")

@app.get("/api/v1/task/{task_id}/status")
async def get_task_status(task_id: str):
    """Get comprehensive task status"""
    try:
        # Check cache first
        cache_key = f"task_status_{task_id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            system_metrics.increment_cache_hits()
            return cached_result
        
        # Cache miss - get from database
        system_metrics.increment_cache_misses()
        system_metrics.increment_database_operations()
        
        # Get task from database using enhanced operations
        task_data = DatabaseOperations.get_task(db_manager, task_id)
        
        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Format response
        task_status = {
            'task_id': task_id,
            'status': task_data.get('status'),
            'task_type': task_data.get('task_type'),
            'created_at': task_data.get('created_at'),
            'assigned_miners': task_data.get('assigned_miners', []),
            'miner_responses': len(task_data.get('miner_responses', [])),
            'required_miner_count': task_data.get('required_miner_count', 0)
        }
        
        # Cache the result
        cache.set(cache_key, task_status)
        
        return task_status
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Get system metrics
        metrics = system_metrics.get_metrics()
        
        # Check file system health
        file_system_healthy = True
        file_system_errors = []
        
        # Check Firebase Cloud Storage health
        file_system_healthy = True
        file_system_errors = []
        
        try:
            # Check if Firebase Cloud Storage is accessible
            storage_stats = await file_manager.get_storage_statistics()
            if 'error' in storage_stats:
                file_system_healthy = False
                file_system_errors.append(f"Firebase Cloud Storage error: {storage_stats['error']}")
                    
        except Exception as e:
            file_system_healthy = False
            file_system_errors.append(f"Firebase Cloud Storage check error: {str(e)}")
        
        # Log health check to wandb
        if wandb_monitor.initialized:
            wandb_monitor.log_system_metrics({
                "health_check": True,
                "file_system_healthy": file_system_healthy,
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": metrics["uptime_seconds"],
                "total_requests": metrics["total_requests"],
                "cache_hit_rate": metrics["cache_hit_rate"],
                "error_rate": metrics["errors"] / max(metrics["total_requests"], 1)
            })
        
        health_status = "healthy" if file_system_healthy else "degraded"
        
        return {
            "status": health_status,
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": metrics["uptime_seconds"],
            "cache_hit_rate": f"{metrics['cache_hit_rate']:.2%}",
            "requests_per_second": f"{metrics['requests_per_second']:.2f}",
            "wandb_active": wandb_monitor.initialized,
            "file_system": {
                "healthy": file_system_healthy,
                "errors": file_system_errors
            }
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/v1/health")
async def api_health_check():
    """API v1 health check endpoint"""
    try:
        # Get system metrics
        metrics = system_metrics.get_metrics()
        
        # Check database connectivity
        db_healthy = True
        db_errors = []
        try:
            if 'db_manager' in globals() and db_manager:
                # Try a simple database operation
                from database.postgresql_adapter import PostgreSQLAdapter
                if isinstance(db_manager, PostgreSQLAdapter):
                    # PostgreSQL: Test connection
                    try:
                        session = db_manager._get_session()
                        session.close()
                        db_healthy = True
                    except:
                        db_healthy = False
                else:
                    # Firestore (legacy)
                    test_collection = db_manager.get_db().collection('health_check')
                    db_healthy = True
            else:
                db_healthy = False
                db_errors.append("Database manager not initialized")
        except Exception as e:
            db_healthy = False
            db_errors.append(f"Database check error: {str(e)}")
        
        # Check file system health
        file_system_healthy = True
        file_system_errors = []
        try:
            if 'file_manager' in globals() and file_manager:
                storage_stats = await file_manager.get_storage_statistics()
                if 'error' in storage_stats:
                    file_system_healthy = False
                    file_system_errors.append(f"Firebase Cloud Storage error: {storage_stats['error']}")
            else:
                file_system_healthy = False
                file_system_errors.append("File manager not initialized")
        except Exception as e:
            file_system_healthy = False
            file_system_errors.append(f"File system check error: {str(e)}")
        
        # Check task manager
        task_manager_healthy = True
        task_manager_errors = []
        try:
            if 'task_manager' in globals() and task_manager:
                task_manager_healthy = True
            else:
                task_manager_healthy = False
                task_manager_errors.append("Task manager not initialized")
        except Exception as e:
            task_manager_healthy = False
            task_manager_errors.append(f"Task manager check error: {str(e)}")
        
        # Check workflow orchestrator
        orchestrator_healthy = True
        orchestrator_errors = []
        try:
            if 'workflow_orchestrator' in globals() and workflow_orchestrator:
                orchestrator_healthy = workflow_orchestrator.running if hasattr(workflow_orchestrator, 'running') else True
            else:
                orchestrator_healthy = False
                orchestrator_errors.append("Workflow orchestrator not initialized")
        except Exception as e:
            orchestrator_healthy = False
            orchestrator_errors.append(f"Orchestrator check error: {str(e)}")
        
        # Overall health status
        overall_healthy = db_healthy and file_system_healthy and task_manager_healthy
        health_status = "healthy" if overall_healthy else "degraded"
        
        # Log health check to wandb
        if wandb_monitor.initialized:
            wandb_monitor.log_system_metrics({
                "health_check": True,
                "api_health_check": True,
                "db_healthy": db_healthy,
                "file_system_healthy": file_system_healthy,
                "task_manager_healthy": task_manager_healthy,
                "orchestrator_healthy": orchestrator_healthy,
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": metrics["uptime_seconds"],
                "total_requests": metrics["total_requests"],
                "cache_hit_rate": metrics["cache_hit_rate"],
                "error_rate": metrics["errors"] / max(metrics["total_requests"], 1)
            })
        
        return {
            "status": health_status,
            "service": "violet-proxy-server",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": metrics["uptime_seconds"],
            "components": {
                "database": {
                    "healthy": db_healthy,
                    "errors": db_errors
                },
                "file_system": {
                    "healthy": file_system_healthy,
                    "errors": file_system_errors
                },
                "task_manager": {
                    "healthy": task_manager_healthy,
                    "errors": task_manager_errors
                },
                "workflow_orchestrator": {
                    "healthy": orchestrator_healthy,
                    "errors": orchestrator_errors
                }
            },
            "metrics": {
                "total_requests": metrics["total_requests"],
                "cache_hit_rate": f"{metrics['cache_hit_rate']:.2%}",
                "requests_per_second": f"{metrics['requests_per_second']:.2f}",
                "total_tasks": metrics["total_tasks"],
                "total_miner_responses": metrics["total_miner_responses"],
                "errors": metrics["errors"]
            },
            "wandb_active": wandb_monitor.initialized
        }
    
    except Exception as e:
        return {
            "status": "error",
            "service": "violet-proxy-server",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        # Log error to wandb
        if wandb_monitor.initialized:
            wandb_monitor.log_system_metrics({
                "health_check_error": True,
                "error_message": str(e),
                "timestamp": datetime.now().isoformat()
            })
        
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/api/v1/files/stats")
async def get_file_stats():
    """Get file storage statistics"""
    try:
        stats = await file_manager.get_storage_statistics()
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.get("/api/v1/files/{file_id}")
async def serve_file(file_id: str):
    """Serve files from R2 Storage"""
    try:
        # Validate file_id parameter
        if not file_id or file_id == "None" or file_id == "null":
            raise HTTPException(status_code=400, detail="Invalid file ID provided")
        
        # Get file metadata first to check for public URL
        file_metadata = await file_manager.get_file_metadata(file_id)
        if not file_metadata:
            raise HTTPException(status_code=404, detail=f"File metadata not found: {file_id}")
        
        # Get file from R2 Storage or use public URL if available
        file_content = await file_manager.download_file(file_id)
        if not file_content:
            # If download fails but we have a public URL, return redirect
            if file_metadata.get('public_url'):
                from fastapi.responses import RedirectResponse
                return RedirectResponse(url=file_metadata['public_url'], status_code=302)
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
        if not file_metadata:
            raise HTTPException(status_code=404, detail=f"File metadata not found: {file_id}")
        
        # Handle Unicode filenames properly
        filename = file_metadata.get('original_filename') or file_metadata.get('file_name', f"{file_id}")
        
        # Create a safe filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        
        # Return file with appropriate headers
        return StreamingResponse(
            iter([file_content]),
            media_type=file_metadata.get('content_type', 'application/octet-stream'),
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")

@app.get("/api/v1/files/{file_id}/download")
async def download_file(file_id: str):
    """Download files from Firebase Cloud Storage with enhanced error handling"""
    try:
        # Validate file_id parameter
        if not file_id or file_id == "None" or file_id == "null":
            raise HTTPException(
                status_code=400, 
                detail="Invalid file ID provided. File ID cannot be None or null."
            )
        
        # Get file metadata first to check for public URL
        file_metadata = await file_manager.get_file_metadata(file_id)
        if not file_metadata:
            raise HTTPException(
                status_code=404, 
                detail=f"File metadata not found for ID: {file_id}"
            )
        
        # Get file from R2 Storage or use public URL if available
        file_content = await file_manager.download_file(file_id)
        if not file_content:
            # If download fails but we have a public URL, return redirect
            if file_metadata.get('public_url'):
                from fastapi.responses import RedirectResponse
                return RedirectResponse(url=file_metadata['public_url'], status_code=302)
            raise HTTPException(
                status_code=404, 
                detail=f"File not found in R2 Storage for ID: {file_id}"
            )
        
        # Determine content type for proper headers
        content_type = file_metadata.get('content_type', 'application/octet-stream')
        
        # Handle Unicode filenames properly
        filename = file_metadata.get('original_filename') or file_metadata.get('file_name', f"{file_id}")
        
        # Create a safe filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        
        # Return file with appropriate headers
        return StreamingResponse(
            iter([file_content]),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Log the error for debugging
        print(f"❌ Error in download_file endpoint: {e}")
        print(f"   File ID: {file_id}")
        print(f"   Error type: {type(e).__name__}")
        
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error while downloading file: {str(e)}"
        )

@app.get("/api/v1/files/list/{file_type}")
async def list_files_by_type(file_type: str):
    """List files by type"""
    try:
        files = await file_manager.list_files_by_type(file_type)
        return {
            "success": True,
            "file_type": file_type,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

# ============================================================================
# Voice Management Endpoints
# ============================================================================

@app.get("/api/v1/voices")
async def list_voices(user_info: dict = Depends(require_client_auth)):
    """List all available voices"""
    try:
        from database.postgresql_schema import Voice
        session = db_manager._get_session()
        try:
            voices = session.query(Voice).all()
            voice_list = []
            for voice in voices:
                voice_list.append({
                    "voice_name": voice.voice_name,
                    "display_name": voice.display_name,
                    "language": voice.language,
                    "public_url": voice.public_url,
                    "file_name": voice.file_name,
                    "file_size": voice.file_size,
                    "file_type": voice.file_type,
                    "created_at": voice.created_at.isoformat() if voice.created_at else None,
                    "updated_at": voice.updated_at.isoformat() if voice.updated_at else None
                })
            return {
                "success": True,
                "count": len(voice_list),
                "voices": voice_list
            }
        finally:
            session.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {str(e)}")

@app.post("/api/v1/voices")
async def add_voice(
    voice_name: str = Form(...),
    display_name: str = Form(...),
    language: str = Form("en"),
    audio_file: UploadFile = File(...),
    user_info: dict = Depends(require_client_auth)
):
    """Add a new voice for TTS voice cloning"""
    try:
        from database.postgresql_schema import Voice
        
        # Validate voice_name (must be unique)
        session = db_manager._get_session()
        try:
            existing_voice = session.query(Voice).filter(Voice.voice_name == voice_name).first()
            if existing_voice:
                raise HTTPException(status_code=400, detail=f"Voice '{voice_name}' already exists")
        finally:
            session.close()
        
        # Validate audio file
        if not audio_file.filename:
            raise HTTPException(status_code=400, detail="Audio file is required")
        
        # Check file extension
        file_ext = os.path.splitext(audio_file.filename)[1].lower()
        if file_ext not in ['.wav', '.mp3', '.flac', '.ogg']:
            raise HTTPException(status_code=400, detail="Audio file must be .wav, .mp3, .flac, or .ogg")
        
        # Read audio file
        audio_data = await audio_file.read()
        if len(audio_data) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        # Upload audio file to R2 storage
        safe_filename = create_safe_filename(audio_file.filename)
        file_id = await file_manager.upload_file(
            audio_data,
            safe_filename,
            audio_file.content_type or "audio/wav",
            file_type="tts_speaker"
        )
        
        # Get file metadata to retrieve public URL
        file_metadata = await file_manager.get_file_metadata(file_id)
        if not file_metadata:
            raise HTTPException(status_code=500, detail="Failed to retrieve file metadata after upload")
        
        public_url = file_metadata.get('public_url')
        if not public_url:
            raise HTTPException(status_code=500, detail="File uploaded but no public URL available")
        
        # Create voice record in database
        session = db_manager._get_session()
        try:
            voice = Voice(
                voice_name=voice_name,
                display_name=display_name,
                language=language,
                file_id=file_id,
                r2_key=file_metadata.get('r2_key'),
                public_url=public_url,
                file_name=safe_filename,
                file_size=len(audio_data),
                file_type=audio_file.content_type or "audio/wav"
            )
            session.add(voice)
            session.commit()
            
            print(f"✅ Voice '{voice_name}' added successfully")
            return {
                "success": True,
                "message": f"Voice '{voice_name}' added successfully",
                "voice": {
                    "voice_name": voice.voice_name,
                    "display_name": voice.display_name,
                    "language": voice.language,
                    "public_url": voice.public_url,
                    "file_id": str(file_id),
                    "file_size": voice.file_size
                }
            }
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create voice record: {str(e)}")
        finally:
            session.close()
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add voice: {str(e)}")

@app.put("/api/v1/voices/{voice_name}")
async def update_voice(
    voice_name: str,
    display_name: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
    user_info: dict = Depends(require_client_auth)
):
    """Update an existing voice"""
    try:
        from database.postgresql_schema import Voice
        
        session = db_manager._get_session()
        try:
            voice = session.query(Voice).filter(Voice.voice_name == voice_name).first()
            if not voice:
                raise HTTPException(status_code=404, detail=f"Voice '{voice_name}' not found")
            
            # Update display_name if provided
            if display_name is not None:
                voice.display_name = display_name
            
            # Update language if provided
            if language is not None:
                voice.language = language
            
            # Update audio file if provided
            if audio_file is not None:
                # Validate audio file
                if not audio_file.filename:
                    raise HTTPException(status_code=400, detail="Audio file is required")
                
                # Check file extension
                file_ext = os.path.splitext(audio_file.filename)[1].lower()
                if file_ext not in ['.wav', '.mp3', '.flac', '.ogg']:
                    raise HTTPException(status_code=400, detail="Audio file must be .wav, .mp3, .flac, or .ogg")
                
                # Read audio file
                audio_data = await audio_file.read()
                if len(audio_data) == 0:
                    raise HTTPException(status_code=400, detail="Audio file is empty")
                
                # Delete old file if it exists
                if voice.file_id:
                    try:
                        await file_manager.delete_file(voice.file_id)
                    except:
                        pass  # Ignore errors when deleting old file
                
                # Upload new audio file to R2 storage
                safe_filename = create_safe_filename(audio_file.filename)
                file_id = await file_manager.upload_file(
                    audio_data,
                    safe_filename,
                    audio_file.content_type or "audio/wav",
                    file_type="tts_speaker"
                )
                
                # Get file metadata to retrieve public URL
                file_metadata = await file_manager.get_file_metadata(file_id)
                if not file_metadata:
                    raise HTTPException(status_code=500, detail="Failed to retrieve file metadata after upload")
                
                public_url = file_metadata.get('public_url')
                if not public_url:
                    raise HTTPException(status_code=500, detail="File uploaded but no public URL available")
                
                # Update voice record
                voice.file_id = file_id
                voice.r2_key = file_metadata.get('r2_key')
                voice.public_url = public_url
                voice.file_name = safe_filename
                voice.file_size = len(audio_data)
                voice.file_type = audio_file.content_type or "audio/wav"
            
            voice.updated_at = datetime.utcnow()
            session.commit()
            
            print(f"✅ Voice '{voice_name}' updated successfully")
            return {
                "success": True,
                "message": f"Voice '{voice_name}' updated successfully",
                "voice": {
                    "voice_name": voice.voice_name,
                    "display_name": voice.display_name,
                    "language": voice.language,
                    "public_url": voice.public_url,
                    "file_id": str(voice.file_id) if voice.file_id else None,
                    "file_size": voice.file_size
                }
            }
        except HTTPException:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update voice: {str(e)}")
        finally:
            session.close()
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update voice: {str(e)}")

@app.delete("/api/v1/voices/{voice_name}")
async def delete_voice(
    voice_name: str,
    user_info: dict = Depends(require_client_auth)
):
    """Delete a voice"""
    try:
        from database.postgresql_schema import Voice
        
        session = db_manager._get_session()
        try:
            voice = session.query(Voice).filter(Voice.voice_name == voice_name).first()
            if not voice:
                raise HTTPException(status_code=404, detail=f"Voice '{voice_name}' not found")
            
            # Delete associated file from R2 storage
            if voice.file_id:
                try:
                    await file_manager.delete_file(voice.file_id)
                except Exception as e:
                    print(f"⚠️ Warning: Failed to delete file {voice.file_id}: {e}")
            
            # Delete voice record
            session.delete(voice)
            session.commit()
            
            print(f"✅ Voice '{voice_name}' deleted successfully")
            return {
                "success": True,
                "message": f"Voice '{voice_name}' deleted successfully"
            }
        except HTTPException:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete voice: {str(e)}")
        finally:
            session.close()
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete voice: {str(e)}")

@app.get("/api/v1/transcription/{task_id}/result")
async def get_transcription_result(task_id: str):
    """Get transcription result for a completed task"""
    try:
        # Get task status
        task_status = await workflow_orchestrator.get_task_status(task_id)
        
        if 'error' in task_status:
            return {
                "success": False,
                "task_id": task_id,
                "message": f"Task not found or unavailable: {task_status.get('error', 'Unknown error')}",
                "status": "not_found",
                "available": False
            }
        
        # Check if task is completed
        task_info = task_status.get('task', {})
        task_status_value = task_info.get('status', 'unknown')
        
        if task_status_value not in ['completed', 'done', 'approved']:
            return {
                "success": False,
                "task_id": task_id,
                "message": f"Task result is not yet available. Current status: {task_status_value}",
                "status": task_status_value,
                "available": False,
                "task_type": task_info.get('task_type', 'unknown'),
                "created_at": task_info.get('created_at'),
                "progress": {
                    "assigned_miners": len(task_info.get('assigned_miners', [])),
                    "miner_responses": task_info.get('miner_responses', 0),
                    "required_miner_count": task_info.get('required_miner_count', 0)
                }
            }
        
        # Get the best response from completion status
        completion_status = task_status.get('completion_status', {})
        miner_statuses = completion_status.get('miner_statuses', {})
        
        # Find the best response (highest accuracy score)
        best_miner_uid = None
        best_accuracy = 0
        
        for miner_uid, status in miner_statuses.items():
            if status.get('status') == 'completed':
                accuracy = status.get('accuracy_score', 0)
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_miner_uid = miner_uid
        
        if not best_miner_uid:
            return {
                "success": False,
                "task_id": task_id,
                "message": "Task is completed but no miner responses are available yet. Please check back shortly.",
                "status": task_status_value,
                "available": False,
                "task_type": task_info.get('task_type', 'unknown'),
                "progress": {
                    "assigned_miners": len(task_info.get('assigned_miners', [])),
                    "miner_responses": task_info.get('miner_responses', 0),
                    "required_miner_count": task_info.get('required_miner_count', 0)
                }
            }
        
        # Get the best miner's response data
        best_status = miner_statuses[best_miner_uid]
        
        # Get transcript from response data
        response_data = best_status.get('response_data', {})
        transcript = response_data.get('output_data', {}).get('transcript', '')
        if not transcript:
            transcript = response_data.get('output_data', {}).get('text', '')
        
        return {
            "success": True,
            "task_id": task_id,
            "status": task_status_value,
            "available": True,
            "transcript": transcript,
            "processing_time": best_status.get('processing_time', 0),
            "miner_uid": int(best_miner_uid),
            "accuracy_score": best_status.get('accuracy_score', 0),
            "speed_score": best_status.get('speed_score', 0),
            "language": response_data.get('output_data', {}).get('language', task_info.get('source_language', 'en')),
            "confidence": response_data.get('output_data', {}).get('confidence', 0.0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get result: {str(e)}")

@app.get("/api/v1/tts/{task_id}/result")
async def get_tts_result(task_id: str):
    """Get TTS result for a completed task"""
    try:
        # Get task status
        task_status = await workflow_orchestrator.get_task_status(task_id)
        
        if 'error' in task_status:
            return {
                "success": False,
                "task_id": task_id,
                "message": f"Task not found or unavailable: {task_status.get('error', 'Unknown error')}",
                "status": "not_found",
                "available": False
            }
        
        # Check if task is completed
        task_info = task_status.get('task', {})
        task_status_value = task_info.get('status', 'unknown')
        
        if task_status_value not in ['completed', 'done', 'approved']:
            return {
                "success": False,
                "task_id": task_id,
                "message": f"Task result is not yet available. Current status: {task_status_value}",
                "status": task_status_value,
                "available": False,
                "task_type": task_info.get('task_type', 'unknown'),
                "created_at": task_info.get('created_at'),
                "progress": {
                    "assigned_miners": len(task_info.get('assigned_miners', [])),
                    "miner_responses": task_info.get('miner_responses', 0),
                    "required_miner_count": task_info.get('required_miner_count', 0)
                }
            }
        
        # Get the best response from completion status
        completion_status = task_status.get('completion_status', {})
        miner_statuses = completion_status.get('miner_statuses', {})
        
        # Find the best response (highest accuracy score)
        best_miner_uid = None
        best_accuracy = 0
        
        for miner_uid, status in miner_statuses.items():
            if status.get('status') == 'completed':
                accuracy = status.get('accuracy_score', 0)
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_miner_uid = miner_uid
        
        if not best_miner_uid:
            return {
                "success": False,
                "task_id": task_id,
                "message": "Task is completed but no miner responses are available yet. Please check back shortly.",
                "status": task_status_value,
                "available": False,
                "task_type": task_info.get('task_type', 'unknown'),
                "progress": {
                    "assigned_miners": len(task_info.get('assigned_miners', [])),
                    "miner_responses": task_info.get('miner_responses', 0),
                    "required_miner_count": task_info.get('required_miner_count', 0)
                }
            }
        
        # Get the best miner's response data
        best_status = miner_statuses[best_miner_uid]
        
        # Get audio file URL if available
        audio_url = f"http://localhost:8000/api/v1/files/tts_audio/{task_id}_{best_miner_uid}.wav"
        
        return {
            "success": True,
            "task_id": task_id,
            "status": task_status_value,
            "available": True,
            "audio_url": audio_url,
            "processing_time": best_status.get('processing_time', 0),
            "miner_uid": int(best_miner_uid),
            "accuracy_score": best_status.get('accuracy_score', 0),
            "speed_score": best_status.get('speed_score', 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get result: {str(e)}")

@app.get("/api/v1/summarization/{task_id}/result")
async def get_summarization_result(task_id: str):
    """Get summarization result for a completed task"""
    try:
        # Get task status
        task_status = await workflow_orchestrator.get_task_status(task_id)
        
        if 'error' in task_status:
            return {
                "success": False,
                "task_id": task_id,
                "message": f"Task not found or unavailable: {task_status.get('error', 'Unknown error')}",
                "status": "not_found",
                "available": False
            }
        
        # Check if task is completed
        task_info = task_status.get('task', {})
        task_status_value = task_info.get('status', 'unknown')
        
        if task_status_value not in ['completed', 'done', 'approved']:
            return {
                "success": False,
                "task_id": task_id,
                "message": f"Task result is not yet available. Current status: {task_status_value}",
                "status": task_status_value,
                "available": False,
                "task_type": "summarization",
                "created_at": task_info.get('created_at'),
                "progress": {
                    "assigned_miners": len(task_info.get('assigned_miners', [])),
                    "miner_responses": task_info.get('miner_responses', 0),
                    "required_miner_count": task_info.get('required_miner_count', 0)
                }
            }
        
        # Get the best response from completion status
        completion_status = task_status.get('completion_status', {})
        miner_statuses = completion_status.get('miner_statuses', {})
        best_response = task_status.get('best_response')
        
        # Find the best response (highest accuracy score)
        best_miner_uid = None
        best_accuracy = 0
        
        for miner_uid, status in miner_statuses.items():
            if status.get('status') == 'completed':
                accuracy = status.get('accuracy_score', 0)
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_miner_uid = miner_uid
        
        if not best_miner_uid and not best_response:
            return {
                "success": False,
                "task_id": task_id,
                "message": "Task is completed but no miner responses are available yet. Please check back shortly.",
                "status": task_status_value,
                "available": False,
                "task_type": "summarization",
                "progress": {
                    "assigned_miners": len(task_info.get('assigned_miners', [])),
                    "miner_responses": task_info.get('miner_responses', 0),
                    "required_miner_count": task_info.get('required_miner_count', 0)
                }
            }
        
        # Get the best miner's response data
        if best_response:
            summary_text = best_response.get('output_data', {}).get('summary', '')
            if not summary_text and isinstance(best_response.get('output_data'), dict):
                summary_text = best_response.get('output_data', {}).get('text', '')
        elif best_miner_uid:
            best_status = miner_statuses[best_miner_uid]
            response_data = best_status.get('response_data', {})
            summary_text = response_data.get('output_data', {}).get('summary', '')
            if not summary_text:
                summary_text = response_data.get('output_data', {}).get('text', '')
        else:
            summary_text = ""
        
        if not summary_text:
            return {
                "success": False,
                "task_id": task_id,
                "message": "Task is completed but summary text is not available. Please check back shortly.",
                "status": task_status_value,
                "available": False,
                "task_type": "summarization"
            }
        
        # Get processing metrics
        processing_time = 0
        accuracy_score = 0
        speed_score = 0
        miner_uid = None
        
        if best_miner_uid:
            best_status = miner_statuses[best_miner_uid]
            processing_time = best_status.get('processing_time', 0)
            accuracy_score = best_status.get('accuracy_score', 0)
            speed_score = best_status.get('speed_score', 0)
            miner_uid = int(best_miner_uid)
        elif best_response:
            processing_time = best_response.get('processing_time', 0)
            accuracy_score = best_response.get('accuracy_score', 0)
            speed_score = best_response.get('speed_score', 0)
            miner_uid = best_response.get('miner_uid')
        
        return {
            "success": True,
            "task_id": task_id,
            "status": task_status_value,
            "available": True,
            "summary": summary_text,
            "processing_time": processing_time,
            "miner_uid": miner_uid,
            "accuracy_score": accuracy_score,
            "speed_score": speed_score,
            "original_text_length": task_info.get('input_text', {}).get('text_length', 0) if task_info.get('input_text') else 0,
            "summary_length": len(summary_text),
            "compression_ratio": round(len(summary_text) / max(task_info.get('input_text', {}).get('text_length', 1), 1), 2) if task_info.get('input_text') else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summarization result: {str(e)}")

@app.get("/api/v1/miners/performance")
async def get_miner_performance():
    """Get comprehensive miner performance metrics"""
    try:
        # Get all completed tasks
        from database.postgresql_adapter import PostgreSQLAdapter
        from database.postgresql_schema import Task, TaskStatusEnum
        
        is_postgresql = isinstance(workflow_orchestrator.db, PostgreSQLAdapter)
        miner_stats = {}
        
        if is_postgresql:
            # PostgreSQL: Get completed tasks
            session = workflow_orchestrator.db._get_session()
            try:
                completed_tasks = session.query(Task).filter(
                    Task.status.in_([TaskStatusEnum.COMPLETED, TaskStatusEnum.APPROVED])
                ).all()
                tasks = [workflow_orchestrator.db._task_to_dict(t) for t in completed_tasks]
            finally:
                session.close()
        else:
            # Firestore (legacy)
            tasks_collection = workflow_orchestrator.db.collection('tasks')
            completed_tasks = tasks_collection.where('status', 'in', ['done', 'approved']).stream()
            tasks = [doc.to_dict() for doc in completed_tasks]
        
        for task in tasks:
            task_id = task.get('task_id')
            if not task_id:
                continue
            
            # Get miner responses for this task
            miner_responses = task.get('miner_responses', [])
            
            for response in miner_responses:
                if isinstance(response, dict):
                    miner_uid = response.get('miner_uid')
                    if not miner_uid:
                        continue
                
                if miner_uid not in miner_stats:
                    miner_stats[miner_uid] = {
                        'total_tasks': 0,
                        'completed_tasks': 0,
                        'total_processing_time': 0,
                        'total_accuracy_score': 0,
                        'total_speed_score': 0,
                        'task_types': {},
                        'recent_performance': []
                    }
                
                miner_stats[miner_uid]['total_tasks'] += 1
                miner_stats[miner_uid]['completed_tasks'] += 1
                miner_stats[miner_uid]['total_processing_time'] += response.get('processing_time', 0)
                miner_stats[miner_uid]['total_accuracy_score'] += response.get('accuracy_score', 0)
                miner_stats[miner_uid]['total_speed_score'] += response.get('speed_score', 0)
                
                # Track task types
                task_type = task.get('task_type', 'unknown')
                if task_type not in miner_stats[miner_uid]['task_types']:
                    miner_stats[miner_uid]['task_types'][task_type] = 0
                miner_stats[miner_uid]['task_types'][task_type] += 1
                
                # Track recent performance
                recent_perf = {
                    'task_id': task_id,
                    'task_type': task_type,
                    'processing_time': response.get('processing_time', 0),
                    'accuracy_score': response.get('accuracy_score', 0),
                    'speed_score': response.get('speed_score', 0),
                    'completed_at': response.get('submitted_at')
                }
                miner_stats[miner_uid]['recent_performance'].append(recent_perf)
        
        # Calculate averages and rankings
        for miner_uid, stats in miner_stats.items():
            if stats['completed_tasks'] > 0:
                stats['avg_processing_time'] = stats['total_processing_time'] / stats['completed_tasks']
                stats['avg_accuracy_score'] = stats['total_accuracy_score'] / stats['completed_tasks']
                stats['avg_speed_score'] = stats['total_speed_score'] / stats['completed_tasks']
                
                # Calculate overall performance score
                stats['overall_score'] = (
                    stats['avg_accuracy_score'] * 0.5 + 
                    stats['avg_speed_score'] * 0.3 + 
                    (1.0 / stats['avg_processing_time']) * 0.2
                )
                
                # Keep only last 10 performance records
                stats['recent_performance'] = sorted(
                    stats['recent_performance'], 
                    key=lambda x: x.get('completed_at', ''), 
                    reverse=True
                )[:10]
        
        # Sort miners by overall performance
        sorted_miners = sorted(
            miner_stats.items(), 
            key=lambda x: x[1].get('overall_score', 0), 
            reverse=True
        )
        
        # Log miner performance to wandb
        if wandb_monitor.initialized:
            for miner_uid, stats in miner_stats.items():
                wandb_monitor.log_miner_performance(int(miner_uid), stats)
            
            # Log overall performance summary
            wandb_monitor.log_system_metrics({
                "miner_performance_summary": {
                    "total_miners": len(miner_stats),
                    "top_performer": sorted_miners[0][0] if sorted_miners else None,
                    "avg_completion_rate": sum(s['completed_tasks'] for s in miner_stats.values()) / len(miner_stats) if miner_stats else 0,
                    "total_tasks_processed": sum(s['completed_tasks'] for s in miner_stats.values())
                }
            })
        
        return {
            "success": True,
            "total_miners": len(miner_stats),
            "miners": dict(sorted_miners),
            "performance_summary": {
                "top_performer": sorted_miners[0][0] if sorted_miners else None,
                "avg_completion_rate": sum(s['completed_tasks'] for s in miner_stats.values()) / len(miner_stats) if miner_stats else 0,
                "total_tasks_processed": sum(s['completed_tasks'] for s in miner_stats.values())
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get miner performance: {str(e)}")

@app.get("/api/v1/miners/{miner_uid}/tasks")
async def get_miner_tasks(
    miner_uid: int,
    status: str = "assigned",
    user_info: dict = Depends(require_miner_auth)
):
    """Get tasks assigned to a specific miner with proper status filtering"""
    try:
        print(f"🔍 Miner {miner_uid} requesting tasks with status: {status}")
        
        # Validate status parameter - miners should only get assigned tasks
        valid_statuses = ["assigned", "pending", "processing"]
        if status not in valid_statuses:
            print(f"⚠️ Invalid status '{status}' requested by miner {miner_uid}. Allowing but logging warning.")
            # Still allow the request but log the warning
        
        # Use enhanced database operations with proper filtering
        tasks = DatabaseOperations.get_miner_tasks(db_manager, miner_uid, status)
        
        # Log what we found
        print(f"📋 Found {len(tasks)} tasks for miner {miner_uid} with status '{status}'")
        
        # Additional validation: ensure we're not returning completed tasks to miners
        filtered_tasks = []
        for task in tasks:
            # Ensure task_id is present (should be added by get_miner_tasks, but double-check)
            if 'task_id' not in task:
                task['task_id'] = task.get('id', 'unknown')
            
            task_status = task.get('status', 'unknown')
            if task_status in ['completed', 'failed', 'cancelled', 'approved']:
                print(f"⚠️ Filtering out {task_status} task {task.get('task_id')} for miner {miner_uid}")
                continue
            filtered_tasks.append(task)
        
        if len(filtered_tasks) != len(tasks):
            print(f"🔍 Filtered {len(tasks) - len(filtered_tasks)} completed/failed tasks from miner {miner_uid} results")
        
        # Log task IDs for debugging
        if filtered_tasks:
            task_ids = [t.get('task_id', 'no_id') for t in filtered_tasks]
            print(f"📋 Returning {len(filtered_tasks)} tasks to miner {miner_uid}: {task_ids}")
        
        return filtered_tasks
        
    except Exception as e:
        print(f"❌ Error getting tasks for miner {miner_uid}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting miner tasks: {str(e)}")

@app.get("/api/v1/task/{task_id}/responses")
async def get_task_responses(task_id: str):
    """Get task information including best response and input details (filtered for client use)"""
    try:
        print(f"🔍 Getting filtered task responses for task: {task_id}")
        
        # Get task from database
        task_data = DatabaseOperations.get_task(db_manager, task_id)
        
        if not task_data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Extract best response
        best_response = task_data.get('best_response', {})
        
        # Format standardized response data based on task type
        task_type = task_data.get('task_type')
        
        if task_type == 'transcription':
            # Standardized transcription response format
            response_data = {
                "task_id": task_id,
                "task_type": task_type,
                "status": task_data.get('status'),
                "created_at": task_data.get('created_at'),
                "best_response": {
                    "output_data": best_response.get('response_data', {}).get('output_data', {}) if best_response else {},
                    "processing_time": best_response.get('processing_time', 0) if best_response else 0,
                    "accuracy_score": best_response.get('accuracy_score', 0) if best_response else 0,
                    "speed_score": best_response.get('speed_score', 0) if best_response else 0
                } if best_response else None,
                "task_summary": {
                    "total_responses_received": len(task_data.get('miner_responses', [])),
                    "required_miner_count": task_data.get('required_miner_count', 1),
                    "task_priority": task_data.get('priority', 'normal')
                }
            }
        else:
            # Fallback format for other task types
            response_data = {
                "task_id": task_id,
                "task_type": task_type,
                "status": task_data.get('status'),
                "created_at": task_data.get('created_at'),
                "best_response": {
                    "response_data": best_response.get('response_data'),
                    "processing_time": best_response.get('processing_time'),
                    "accuracy_score": best_response.get('accuracy_score'),
                    "speed_score": best_response.get('speed_score'),
                    "submitted_at": best_response.get('submitted_at')
                } if best_response else None,
                "task_summary": {
                    "total_responses_received": len(task_data.get('miner_responses', [])),
                    "required_miner_count": task_data.get('required_miner_count', 1),
                    "task_priority": task_data.get('priority', 'normal')
                }
            }
        
        print(f"✅ Retrieved filtered task information for task {task_id}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting task responses: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task responses: {str(e)}")

@app.get("/api/v1/tasks/completed")
async def get_completed_tasks():
    """Get all completed tasks for validator evaluation"""
    try:
        print(f"🔍 Getting completed tasks for validator evaluation")
        
        # Get all completed tasks from database
        # Note: get_tasks_by_status returns dictionaries for PostgreSQL, Firestore documents for Firestore
        completed_tasks = DatabaseOperations.get_tasks_by_status(db_manager, TaskStatus.COMPLETED, limit=100)
        
        tasks = []
        for task_doc in completed_tasks:
            # Handle both PostgreSQL (dict) and Firestore (document) cases
            if isinstance(task_doc, dict):
                # Already a dictionary (PostgreSQL)
                task_data = task_doc.copy()
                # Ensure task_id is present
                if 'task_id' not in task_data:
                    task_data['task_id'] = task_data.get('id', 'unknown')
            else:
                # Firestore document - convert to dict
                task_data = task_doc.to_dict()
                task_data['task_id'] = task_doc.id
            
            # Ensure miner_responses is included for evaluation
            if 'miner_responses' not in task_data:
                task_data['miner_responses'] = []
            
            tasks.append(task_data)
        
        print(f"✅ Retrieved {len(tasks)} completed tasks for validator evaluation")
        return tasks
        
    except Exception as e:
        print(f"❌ Error getting completed tasks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get completed tasks: {str(e)}")

@app.post("/api/v1/miners/register")
async def register_miner(
    uid: int = Form(...),
    hotkey: str = Form(...),
    stake: float = Form(1000.0),
    is_serving: bool = Form(True),
    task_type_specialization: str = Form(""),
    max_capacity: int = Form(100)
):
    """Register a new miner or update existing one"""
    try:
        # Create miner data
        miner_data = {
            'uid': uid,
            'hotkey': hotkey,
            'stake': stake,
            'is_serving': is_serving,
            'task_type_specialization': task_type_specialization,
            'max_capacity': max_capacity,
            'current_load': 0,
            'registered_at': datetime.now(),
            'last_seen': datetime.now()
        }
        
        # Register miner in database
        success = DatabaseOperations.register_miner(db_manager, miner_data)
        
        if success:
            print(f"✅ Miner {uid} registered successfully")
            return {
                "success": True,
                "message": f"Miner {uid} registered successfully",
                "miner_data": miner_data
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to register miner")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register miner: {str(e)}")

@app.get("/api/v1/miners")
async def get_miners(
    user_info: dict = Depends(require_client_auth)
):
    """Get all active miners from validator reports (miner_status collection)"""
    try:
        from datetime import datetime
        from dateutil import parser
        
        print(f"🔍 GET /api/v1/miners - Fetching active miners from miner_status collection")
        
        # Query miner_status collection (where validators send active miners)
        from database.postgresql_adapter import PostgreSQLAdapter
        from database.postgresql_schema import MinerStatus
        
        is_postgresql = isinstance(db_manager, PostgreSQLAdapter)
        current_time = datetime.utcnow()
        miner_timeout = 900  # 15 minutes - same as network-status endpoint
        
        miners = []
        stale_count = 0
        
        if is_postgresql:
            # PostgreSQL: Query miner status
            session = db_manager._get_session()
            try:
                miner_statuses = session.query(MinerStatus).all()
                docs = [db_manager._miner_status_to_dict(m) for m in miner_statuses]
            finally:
                session.close()
        else:
            # Firestore (legacy)
            db = db_manager.get_db()
            miner_status_collection = db.collection('miner_status')
            docs = miner_status_collection.stream()
        
        for doc in docs:
            try:
                if is_postgresql:
                    miner_data = doc  # Already a dict
                    miner_data['miner_id'] = str(miner_data.get('uid', ''))
                else:
                    miner_data = doc.to_dict()
                    # CRITICAL: Add miner_id from document ID
                    miner_data['miner_id'] = doc.id
                
                # Ensure uid is present
                if 'uid' not in miner_data:
                    miner_data['uid'] = miner_data.get('miner_id')
                
                # Filter out stale miners (not seen in last 15 minutes)
                last_seen = miner_data.get('last_seen')
                timestamp_to_check = last_seen or miner_data.get('last_updated')
                
                if timestamp_to_check:
                    try:
                        # Normalize current_time to timezone-naive for comparison
                        current_time_naive = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time
                        
                        # Handle different timestamp formats and normalize to timezone-naive
                        if isinstance(timestamp_to_check, datetime):
                            # Normalize to timezone-naive
                            ts_naive = timestamp_to_check.replace(tzinfo=None) if timestamp_to_check.tzinfo else timestamp_to_check
                            time_diff = (current_time_naive - ts_naive).total_seconds()
                        elif hasattr(timestamp_to_check, 'replace'):
                            # Firestore DatetimeWithNanoseconds or similar
                            try:
                                ts_naive = timestamp_to_check.replace(tzinfo=None)
                                time_diff = (current_time_naive - ts_naive).total_seconds()
                            except:
                                # Fallback: try timestamp method
                                if hasattr(timestamp_to_check, 'timestamp'):
                                    time_diff = (current_time_naive.timestamp() - timestamp_to_check.timestamp())
                                else:
                                    # Unknown format, skip timestamp check but include miner
                                    time_diff = 0
                        elif hasattr(timestamp_to_check, 'timestamp'):
                            # Firestore Timestamp object
                            ts_naive = datetime.fromtimestamp(timestamp_to_check.timestamp())
                            time_diff = (current_time_naive - ts_naive).total_seconds()
                        elif isinstance(timestamp_to_check, str):
                            # ISO format string
                            last_seen_dt = parser.parse(timestamp_to_check)
                            # Normalize to timezone-naive
                            ts_naive = last_seen_dt.replace(tzinfo=None) if last_seen_dt.tzinfo else last_seen_dt
                            time_diff = (current_time_naive - ts_naive).total_seconds()
                        else:
                            # Unknown format, skip timestamp check but include miner
                            time_diff = 0
                        
                        # Only include miners seen within the timeout period
                        if time_diff > miner_timeout:
                            minutes_ago = time_diff / 60
                            print(f"⏰ Filtering stale miner {miner_data.get('uid')} - last seen {minutes_ago:.1f} minutes ago")
                            stale_count += 1
                            continue
                    except Exception as e:
                        print(f"⚠️ Error checking timestamp for miner {miner_data.get('uid')}: {e}")
                        import traceback
                        traceback.print_exc()
                        # Include miner anyway if timestamp parsing fails (better to show than hide)
                        pass
                
                miners.append(miner_data)
                
            except Exception as e:
                print(f"⚠️ Error processing miner document {doc.id}: {e}")
                continue
        
        print(f"📋 Found {len(miners)} active miners (filtered {stale_count} stale miners)")
        
        return {
            "success": True,
            "miners": miners,
            "count": len(miners),
            "stale_filtered": stale_count
        }
        
    except Exception as e:
        print(f"❌ Error getting miners: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get miners: {str(e)}")

@app.get("/api/v1/tasks")
async def get_all_tasks(
    user_info: dict = Depends(require_client_auth)
):
    """Get all tasks - queries all tasks regardless of status"""
    try:
        from database.enhanced_schema import COLLECTIONS
        
        print(f"🔍 GET /api/v1/tasks - Fetching all tasks from database")
        
        # Query ALL tasks directly instead of filtering by status
        # This is more reliable and catches tasks with any status value
        from database.postgresql_adapter import PostgreSQLAdapter
        from database.postgresql_schema import Task
        
        is_postgresql = isinstance(db_manager, PostgreSQLAdapter)
        all_tasks = []
        status_counts = {}
        error_count = 0
        
        if is_postgresql:
            # PostgreSQL: Get all tasks
            session = db_manager._get_session()
            try:
                tasks = session.query(Task).limit(1000).all()
                for task in tasks:
                    try:
                        task_data = db_manager._task_to_dict(task)
                        all_tasks.append(task_data)
                        
                        # Track status distribution
                        task_status = task_data.get('status', 'unknown')
                        if hasattr(task_status, 'value'):
                            task_status = task_status.value
                        status_counts[task_status] = status_counts.get(task_status, 0) + 1
                    except Exception as e:
                        error_count += 1
                        print(f"⚠️ Error processing task {task.task_id}: {e}")
            finally:
                session.close()
        else:
            # Firestore (legacy)
            db = db_manager.get_db()
            tasks_collection = db.collection(COLLECTIONS.get('tasks', 'tasks'))
            docs = tasks_collection.limit(1000).stream()
            
            for doc in docs:
                try:
                    task_data = doc.to_dict()
                    if task_data:
                        task_data['task_id'] = doc.id
                        all_tasks.append(task_data)
                        
                        task_status = task_data.get('status', 'unknown')
                        if hasattr(task_status, 'value'):
                            task_status = task_status.value
                        status_counts[task_status] = status_counts.get(task_status, 0) + 1
                except Exception as e:
                    error_count += 1
                    print(f"⚠️ Error processing task document {doc.id}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        print(f"📋 Found {len(all_tasks)} total tasks in database")
        if status_counts:
            print(f"   Status distribution: {status_counts}")
        if error_count > 0:
            print(f"   ⚠️ {error_count} documents had errors during processing")
        
        return all_tasks
        
    except Exception as e:
        print(f"❌ Error getting all tasks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get tasks: {str(e)}")

@app.get("/api/v1/tasks/{task_id}")
async def get_task_by_id(task_id: str):
    """Get specific task by ID"""
    try:
        task = DatabaseOperations.get_task(db_manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")

@app.get("/api/v1/metrics")
async def get_metrics():
    """Get system metrics and statistics"""
    try:
        # Get basic system metrics
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "system_status": "healthy",
            "duplicate_protection": {},
            "network_miners": {}
        }
        
        # Get duplicate protection statistics from all levels
        try:
            # Level 1: Miner-level protection stats
            miner_stats = {
                "level": "miner",
                "description": "In-memory task tracking and processing state management",
                "status": "active"
            }
            metrics["duplicate_protection"]["miner_level"] = miner_stats
            
            # Level 2: Proxy server-level protection stats
            if hasattr(app.state, 'miner_response_handler'):
                proxy_stats = app.state.miner_response_handler.get_duplicate_protection_stats()
                metrics["duplicate_protection"]["proxy_level"] = proxy_stats
            else:
                metrics["duplicate_protection"]["proxy_level"] = {"status": "not_initialized"}
            
            # Level 3: Task distributor-level protection stats
            if hasattr(app.state, 'task_distributor'):
                distributor_stats = app.state.task_distributor.get_duplicate_protection_stats()
                metrics["duplicate_protection"]["distributor_level"] = distributor_stats
            else:
                metrics["duplicate_protection"]["distributor_level"] = {"status": "not_initialized"}
            
            # Overall duplicate protection summary
            total_protected = 0
            total_effectiveness = 0
            active_levels = 0
            
            for level, stats in metrics["duplicate_protection"].items():
                if isinstance(stats, dict) and stats.get("status") == "active":
                    active_levels += 1
                    if "duplicate_protection_effectiveness" in stats:
                        effectiveness_str = stats["duplicate_protection_effectiveness"]
                        try:
                            effectiveness = float(effectiveness_str.rstrip('%'))
                            total_effectiveness += effectiveness
                        except:
                            pass
            
            metrics["duplicate_protection"]["summary"] = {
                "active_protection_levels": active_levels,
                "total_protection_levels": 3,
                "overall_effectiveness": f"{(total_effectiveness / max(active_levels, 1)):.2f}%" if active_levels > 0 else "0%",
                "protection_status": "fully_active" if active_levels == 3 else "partially_active"
            }
            
        except Exception as e:
            metrics["duplicate_protection"]["error"] = f"Error getting protection stats: {str(e)}"
        
        # Get network miner status
        try:
            if hasattr(app.state, 'miner_status_manager'):
                available_miners = await app.state.miner_status_manager.get_available_miners()
                
                # Calculate network statistics
                total_miners = len(available_miners)
                active_miners = len([m for m in available_miners if m.get('is_serving', True)])
                total_stake = sum(float(m.get('stake', 0)) for m in available_miners)
                avg_performance = sum(m.get('performance_score', 0) for m in available_miners) / max(total_miners, 1)
                
                metrics["network_miners"] = {
                    "total_miners": total_miners,
                    "active_miners": active_miners,
                    "total_stake": total_stake,
                    "average_performance_score": round(avg_performance, 3),
                    "miner_details": [
                        {
                            "uid": m.get('uid'),
                            "hotkey": m.get('hotkey', 'unknown')[:10] + '...' if m.get('hotkey') else 'unknown',
                            "stake": m.get('stake', 0),
                            "availability_score": m.get('availability_score', 0),
                            "current_load": m.get('current_load', 0),
                            "max_capacity": m.get('max_capacity', 5)
                        }
                        for m in available_miners[:10]  # Show top 10 miners
                    ]
                }
            else:
                metrics["network_miners"] = {"status": "not_initialized"}
                
        except Exception as e:
            metrics["network_miners"]["error"] = f"Error getting network miner status: {str(e)}"
        
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting metrics: {str(e)}")

@app.get("/api/v1/metrics/json")
async def get_system_metrics_json():
    """Get system metrics in JSON format"""
    try:
        metrics = system_metrics.get_metrics()
        
        # Log to wandb
        wandb_monitor.log_system_metrics(metrics)
        
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@app.get("/api/v1/duplicate-protection/stats")
async def get_duplicate_protection_stats():
    """Get detailed duplicate protection statistics from all levels"""
    try:
        stats = {
            "timestamp": datetime.now().isoformat(),
            "duplicate_protection_system": {
                "description": "Multi-level duplicate protection system to prevent miners from processing the same task multiple times",
                "total_levels": 3,
                "levels": {}
            }
        }
        
        # Level 1: Miner-level protection
        stats["duplicate_protection_system"]["levels"]["miner_level"] = {
            "name": "Miner-Level Protection",
            "description": "In-memory task tracking and processing state management",
            "mechanisms": [
                "processed_tasks set - tracks completed tasks",
                "processing_tasks set - tracks currently processing tasks",
                "Task status validation before processing",
                "Automatic cleanup of old processed tasks"
            ],
            "status": "active",
            "effectiveness": "Prevents miner from processing same task multiple times"
        }
        
        # Level 2: Proxy server-level protection
        if hasattr(app.state, 'miner_response_handler'):
            proxy_stats = app.state.miner_response_handler.get_duplicate_protection_stats()
            stats["duplicate_protection_system"]["levels"]["proxy_level"] = {
                "name": "Proxy Server-Level Protection",
                "description": "Duplicate response detection and prevention",
                "mechanisms": [
                    "Check for existing miner responses before storing",
                    "Race condition protection with double-checking",
                    "Automatic duplicate response rejection"
                ],
                "status": "active",
                "statistics": proxy_stats
            }
        else:
            stats["duplicate_protection_system"]["levels"]["proxy_level"] = {
                "name": "Proxy Server-Level Protection",
                "description": "Duplicate response detection and prevention",
                "status": "not_initialized",
                "error": "Miner response handler not available"
            }
        
        # Level 3: Task distributor-level protection
        if hasattr(app.state, 'task_distributor'):
            distributor_stats = app.state.task_distributor.get_duplicate_protection_stats()
            stats["duplicate_protection_system"]["levels"]["distributor_level"] = {
                "name": "Task Distributor-Level Protection",
                "description": "Prevent distribution of already assigned/completed tasks",
                "mechanisms": [
                    "Task status validation before distribution",
                    "Skip tasks with invalid statuses",
                    "Prevent duplicate task assignments"
                ],
                "status": "active",
                "statistics": distributor_stats
            }
        else:
            stats["duplicate_protection_system"]["levels"]["distributor_level"] = {
                "name": "Task Distributor-Level Protection",
                "description": "Prevent distribution of already assigned/completed tasks",
                "status": "not_initialized",
                "error": "Task distributor not available"
            }
        
        # Overall system health
        active_levels = sum(1 for level in stats["duplicate_protection_system"]["levels"].values() 
                          if level.get("status") == "active")
        
        stats["duplicate_protection_system"]["overall_health"] = {
            "active_levels": active_levels,
            "total_levels": 3,
            "health_percentage": f"{(active_levels / 3) * 100:.1f}%",
            "status": "fully_healthy" if active_levels == 3 else "partially_healthy" if active_levels > 0 else "unhealthy"
        }
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting duplicate protection stats: {str(e)}")

# Enhanced multi-validator miner status endpoint
@app.post("/api/v1/validators/miner-status")
async def receive_miner_status_from_validator(
    validator_uid: int = Form(...),
    miner_statuses: str = Form(...),  # JSON string
    epoch: int = Form(...),
    user_info: dict = Depends(require_validator_auth)
):
    """Receive miner status reports from validators with multi-validator consensus"""
    try:
        import json
        miner_data = json.loads(miner_statuses)
        
        print(f"📥 Received miner status from validator {validator_uid} for epoch {epoch}")
        print(f"   Miners reported: {len(miner_data)}")
        
        # Simplified: Just update miner status from validator report (no consensus tracking)
        # Validators handle consensus via weight setting, proxy just needs availability
        result = await _legacy_miner_status_processing(validator_uid, miner_data, epoch)
        
        # Track metrics
        system_metrics.increment_database_operations()
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON from validator {validator_uid}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON data: {str(e)}")
    except ModuleNotFoundError as e:
        print(f"❌ Missing module error processing miner status from validator {validator_uid}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Missing required module: {str(e)}. Please install python-dateutil: pip install python-dateutil"
        )
    except Exception as e:
        print(f"❌ Error processing miner status from validator {validator_uid}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process miner status: {str(e)}")

async def _legacy_miner_status_processing(validator_uid: int, miner_data: List[Dict], epoch: int) -> Dict[str, Any]:
    """Legacy single-validator miner status processing"""
    try:
        updated_count = 0
        for miner_status in miner_data:
            try:
                miner_uid = miner_status.get('uid')
                if miner_uid is not None:
                    # Add timestamp and validator info
                    # Convert ISO string timestamps to datetime objects if needed
                    if 'last_seen' in miner_status and isinstance(miner_status['last_seen'], str):
                        try:
                            from dateutil import parser
                            miner_status['last_seen'] = parser.parse(miner_status['last_seen'])
                        except:
                            miner_status['last_seen'] = datetime.utcnow()
                    else:
                        miner_status['last_seen'] = datetime.utcnow()  # Ensure last_seen is set
                    
                    miner_status['updated_at'] = datetime.utcnow()
                    miner_status['reported_by_validator'] = validator_uid
                    miner_status['epoch'] = epoch
                    
                    # Ensure uid is set
                    if 'uid' not in miner_status:
                        miner_status['uid'] = miner_uid
                    
                    # Store in database
                    from database.postgresql_adapter import PostgreSQLAdapter
                    if isinstance(db_manager, PostgreSQLAdapter):
                        # PostgreSQL: Update or create miner status
                        from database.postgresql_schema import MinerStatus
                        session = db_manager._get_session()
                        try:
                            existing = session.query(MinerStatus).filter(MinerStatus.uid == miner_uid).first()
                            if existing:
                                # Update existing
                                for key, value in miner_status.items():
                                    if hasattr(existing, key):
                                        setattr(existing, key, value)
                                existing.updated_at = datetime.utcnow()
                            else:
                                # Create new
                                new_status = MinerStatus(**{k: v for k, v in miner_status.items() if hasattr(MinerStatus, k)})
                                session.add(new_status)
                            session.commit()
                        finally:
                            session.close()
                    else:
                        # Firestore (legacy)
                        miner_ref = db_manager.get_db().collection('miner_status').document(str(miner_uid))
                        miner_status['last_updated'] = datetime.utcnow()
                        miner_ref.set(miner_status, merge=True)
                    
                    print(f"      ✅ Updated miner {miner_uid} in miner_status collection")
                    updated_count += 1
                    
                    print(f"      ✅ Updated miner {miner_uid}: {miner_status.get('hotkey', 'unknown')}")
                else:
                    print(f"      ⚠️ Skipping miner without UID: {miner_status}")
                    
            except Exception as e:
                print(f"      ❌ Error updating miner {miner_status.get('uid', 'unknown')}: {e}")
                continue
        
        print(f"   Successfully updated {updated_count}/{len(miner_data)} miners (legacy mode)")
        
        return {
            "success": True, 
            "miners_updated": updated_count,
            "total_received": len(miner_data),
            "validator_uid": validator_uid,
            "epoch": epoch,
            "processing_mode": "legacy"
        }
        
    except Exception as e:
        print(f"❌ Error in legacy miner status processing: {e}")
        return {
            "success": False,
            "error": str(e),
            "validator_uid": validator_uid,
            "processing_mode": "legacy"
        }

# Add endpoint to get current miner status
@app.get("/api/v1/miners/network-status")
async def get_network_miner_status(
    user_info: dict = Depends(require_client_auth)
):
    """Get current miner status from Bittensor network (via validator reports) - only shows active miners"""
    try:
        from datetime import datetime, timedelta
        from dateutil import parser
        
        # Query miner status collection
        from database.postgresql_adapter import PostgreSQLAdapter
        from database.postgresql_schema import MinerStatus
        
        is_postgresql = isinstance(db_manager, PostgreSQLAdapter)
        current_time = datetime.utcnow()
        miner_timeout = 900  # 15 minutes - same as cleanup timeout
        
        miners = []
        stale_count = 0
        
        if is_postgresql:
            # PostgreSQL: Query miner status
            session = db_manager._get_session()
            try:
                miner_statuses = session.query(MinerStatus).all()
                docs = [db_manager._miner_status_to_dict(m) for m in miner_statuses]
            finally:
                session.close()
        else:
            # Firestore (legacy)
            miner_status_collection = db_manager.get_db().collection('miner_status')
            docs = miner_status_collection.stream()
        
        for doc in docs:
            if is_postgresql:
                miner_data = doc  # Already a dict
            else:
                miner_data = doc.to_dict()
            last_seen = miner_data.get('last_seen')
            
            # Filter out stale miners (not seen in last 15 minutes)
            # Try last_seen first, then fall back to last_updated
            timestamp_to_check = last_seen or miner_data.get('last_updated')
            
            if timestamp_to_check:
                try:
                    # Normalize current_time to timezone-naive for comparison
                    current_time_naive = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time
                    
                    # Handle different timestamp formats and normalize to timezone-naive
                    if isinstance(timestamp_to_check, datetime):
                        # Normalize to timezone-naive
                        ts_naive = timestamp_to_check.replace(tzinfo=None) if timestamp_to_check.tzinfo else timestamp_to_check
                        time_diff = (current_time_naive - ts_naive).total_seconds()
                    elif hasattr(timestamp_to_check, 'replace'):  # DatetimeWithNanoseconds or similar datetime-like
                        # It's a datetime-like object (Firestore DatetimeWithNanoseconds)
                        try:
                            ts_naive = timestamp_to_check.replace(tzinfo=None)
                            time_diff = (current_time_naive - ts_naive).total_seconds()
                        except Exception as replace_error:
                            # If replace fails, try converting via timestamp
                            try:
                                if hasattr(timestamp_to_check, 'timestamp'):
                                    ts_naive = datetime.fromtimestamp(timestamp_to_check.timestamp())
                                    time_diff = (current_time_naive - ts_naive).total_seconds()
                                else:
                                    raise replace_error
                            except:
                                raise replace_error
                    elif hasattr(timestamp_to_check, 'timestamp'):  # Firestore Timestamp
                        # It's a timestamp object
                        ts_naive = datetime.fromtimestamp(timestamp_to_check.timestamp())
                        time_diff = (current_time_naive - ts_naive).total_seconds()
                    elif isinstance(timestamp_to_check, str):
                        try:
                            last_seen_dt = parser.parse(timestamp_to_check)
                            # Normalize to timezone-naive
                            ts_naive = last_seen_dt.replace(tzinfo=None) if last_seen_dt.tzinfo else last_seen_dt
                            time_diff = (current_time_naive - ts_naive).total_seconds()
                        except Exception as parse_error:
                            print(f"⚠️  Error parsing timestamp string '{timestamp_to_check}': {parse_error}")
                            stale_count += 1
                            continue
                    else:
                        # Try to convert unknown type to datetime
                        try:
                            if hasattr(timestamp_to_check, 'replace'):
                                # DatetimeWithNanoseconds or similar
                                ts_naive = timestamp_to_check.replace(tzinfo=None)
                                time_diff = (current_time_naive - ts_naive).total_seconds()
                            else:
                                print(f"⚠️  Unknown timestamp format for miner {miner_data.get('uid')}: {type(timestamp_to_check)}")
                                stale_count += 1
                                continue
                        except Exception as conv_error:
                            print(f"⚠️  Error converting timestamp for miner {miner_data.get('uid')}: {conv_error}")
                            stale_count += 1
                            continue
                    
                    # Only include miners seen within the timeout period
                    if time_diff > miner_timeout:
                        minutes_ago = time_diff / 60
                        print(f"⏰ Filtering stale miner {miner_data.get('uid')} - last seen {minutes_ago:.1f} minutes ago")
                        stale_count += 1
                        continue  # Skip stale miners
                except Exception as e:
                    print(f"⚠️  Error checking timestamp for miner {miner_data.get('uid')}: {e}")
                    import traceback
                    traceback.print_exc()
                    stale_count += 1
                    continue  # Skip miners with timestamp parsing errors
            else:
                # No timestamp at all - mark as stale
                print(f"⚠️  Miner {miner_data.get('uid')} has no timestamp - filtering out")
                stale_count += 1
                continue  # Skip miners with no timestamp
            
            miner_data['miner_id'] = doc.id
            miners.append(miner_data)
        
        # Calculate network statistics (only for active miners)
        total_miners = len(miners)
        active_miners = len([m for m in miners if m.get('is_serving', False)])
        total_stake = sum(float(m.get('stake', 0)) for m in miners)
        
        return {
            "success": True,
            "network_status": {
                "total_miners": total_miners,
                "active_miners": active_miners,
                "total_stake": total_stake,
                "stale_miners_filtered": stale_count,
                "last_updated": datetime.now().isoformat()
            },
            "miners": miners
        }
        
    except Exception as e:
        print(f"❌ Error getting network miner status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get miner status: {str(e)}")

# New endpoint to get multi-validator consensus statistics
@app.get("/api/v1/validators/consensus-stats")
async def get_validator_consensus_stats():
    """Get statistics about multi-validator consensus and reports"""
    try:
        if not hasattr(app.state, 'multi_validator_manager'):
            raise HTTPException(status_code=503, detail="Multi-validator manager not available")
        
        stats = await app.state.multi_validator_manager.get_validator_report_stats()
        
        return {
            "success": True,
            "consensus_statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting consensus stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get consensus stats: {str(e)}")

# New endpoint to get consensus status for a specific miner
@app.get("/api/v1/miners/{miner_uid}/consensus")
async def get_miner_consensus_status(miner_uid: int):
    """Get consensus status for a specific miner"""
    try:
        if not hasattr(app.state, 'multi_validator_manager'):
            raise HTTPException(status_code=503, detail="Multi-validator manager not available")
        
        consensus_status = await app.state.multi_validator_manager.get_consensus_miner_status(miner_uid)
        
        if consensus_status:
            return {
                "success": True,
                "miner_uid": miner_uid,
                "consensus_status": consensus_status,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail=f"No consensus status found for miner {miner_uid}")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting miner consensus status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get miner consensus status: {str(e)}")

# ============================================================================
# ADMIN/MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/v1/admin/tasks/complete-stale")
async def complete_stale_tasks(
    user_info: dict = Depends(require_client_auth)
):
    """
    Manually trigger completion of stale tasks with partial responses.
    Tasks with at least 1 response that are > 1 hour old will be marked as completed.
    """
    try:
        if not hasattr(app.state, 'workflow_orchestrator'):
            raise HTTPException(status_code=500, detail="Workflow orchestrator not initialized")
        
        result = await app.state.workflow_orchestrator.handle_stale_tasks_manual()
        
        completed_count = result.get('completed_count', 0)
        failed_count = result.get('failed_count', 0)
        total_processed = completed_count + failed_count
        
        return {
            "success": result.get('success', False),
            "message": f"Processed {total_processed} stale tasks: {completed_count} completed, {failed_count} failed",
            "statistics": {
                "completed_count": completed_count,
                "failed_count": failed_count,
                "skipped_count": result.get('skipped_count', 0),
                "total_checked": result.get('total_checked', 0),
                "completed_task_ids": result.get('completed_task_ids', []),
                "failed_task_ids": result.get('failed_task_ids', [])
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error completing stale tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete stale tasks: {str(e)}")

@app.get("/api/v1/admin/tasks/stale-stats")
async def get_stale_tasks_stats(
    user_info: dict = Depends(require_client_auth)  # Use client auth for now, can be changed to admin
):
    """
    Get statistics about stale tasks (assigned tasks > 1 hour old with partial responses).
    """
    try:
        from database.postgresql_schema import Task, TaskStatusEnum
        from datetime import timedelta
        
        one_hour_ago = datetime.now() - timedelta(hours=1)
        session = db_manager._get_session()
        
        try:
            # Get stale assigned tasks
            stale_assigned_tasks = session.query(Task).filter(
                Task.status == TaskStatusEnum.ASSIGNED,
                Task.created_at < one_hour_ago
            ).all()
            
            # Get stale pending tasks (never assigned)
            stale_pending_tasks = session.query(Task).filter(
                Task.status == TaskStatusEnum.PENDING,
                Task.created_at < one_hour_ago
            ).all()
            
            stats = {
                'total_stale_assigned_tasks': len(stale_assigned_tasks),
                'total_stale_pending_tasks': len(stale_pending_tasks),
                'total_stale_tasks': len(stale_assigned_tasks) + len(stale_pending_tasks),
                'assigned_tasks_with_responses': 0,
                'assigned_tasks_without_responses': 0,
                'total_responses': 0,
                'oldest_task_age_hours': 0,
                'newest_task_age_hours': 0
            }
            
            all_stale_tasks = stale_assigned_tasks + stale_pending_tasks
            
            if all_stale_tasks:
                oldest_task = min(all_stale_tasks, key=lambda t: t.created_at)
                newest_task = max(all_stale_tasks, key=lambda t: t.created_at)
                
                oldest_age = (datetime.now() - oldest_task.created_at).total_seconds() / 3600
                newest_age = (datetime.now() - newest_task.created_at).total_seconds() / 3600
                
                stats['oldest_task_age_hours'] = round(oldest_age, 2)
                stats['newest_task_age_hours'] = round(newest_age, 2)
                
                # Process assigned tasks
                for task in stale_assigned_tasks:
                    miner_responses = task.miner_responses if hasattr(task, 'miner_responses') else []
                    if isinstance(miner_responses, str):
                        import json
                        try:
                            miner_responses = json.loads(miner_responses)
                        except:
                            miner_responses = []
                    response_count = len(miner_responses) if isinstance(miner_responses, list) else 0
                    
                    if response_count >= 1:
                        stats['assigned_tasks_with_responses'] += 1
                        stats['total_responses'] += response_count
                    else:
                        stats['assigned_tasks_without_responses'] += 1
            
            return {
                "success": True,
                "statistics": stats,
                "timestamp": datetime.now().isoformat()
            }
            
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ Error getting stale tasks stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stale tasks stats: {str(e)}")

# ============================================================================
# LEADERBOARD ENDPOINTS
# ============================================================================

@app.get("/api/v1/leaderboard")
async def get_leaderboard(
    limit: int = 100,
    sort_by: str = "overall_score",
    order: str = "desc",
    user_info: dict = Depends(require_client_auth)
):
    """
    Get comprehensive miner leaderboard with all metrics.
    
    Query Parameters:
    - limit: Maximum number of miners to return (default: 100)
    - sort_by: Field to sort by (default: overall_score)
        Options: overall_score, uptime_score, invocation_count, diversity_count, 
                 bounty_count, total_tasks_completed, average_response_time
    - order: Sort order - "asc" or "desc" (default: desc)
    
    Returns:
    - Comprehensive leaderboard with all miner metrics, rankings, and statistics
    """
    try:
        global leaderboard_api
        if not leaderboard_api:
            raise HTTPException(status_code=500, detail="Leaderboard API not initialized")
        
        leaderboard = await leaderboard_api.get_leaderboard(
            limit=limit,
            sort_by=sort_by,
            order=order
        )
        
        return {
            "success": True,
            "leaderboard": leaderboard,
            "total_miners": len(leaderboard),
            "sort_by": sort_by,
            "order": order,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get leaderboard: {str(e)}")

@app.get("/api/v1/leaderboard/{miner_uid}")
async def get_miner_leaderboard_position(
    miner_uid: int,
    user_info: dict = Depends(require_client_auth)
):
    """
    Get a specific miner's leaderboard position and metrics.
    """
    try:
        global leaderboard_api
        if not leaderboard_api:
            raise HTTPException(status_code=500, detail="Leaderboard API not initialized")
        
        # Get full leaderboard
        leaderboard = await leaderboard_api.get_leaderboard(limit=1000)
        
        # Find miner in leaderboard
        miner_entry = None
        for entry in leaderboard:
            if entry.get('uid') == miner_uid:
                miner_entry = entry
                break
        
        if not miner_entry:
            raise HTTPException(status_code=404, detail=f"Miner {miner_uid} not found in leaderboard")
        
        return {
            "success": True,
            "miner": miner_entry,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting miner leaderboard position: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get miner leaderboard position: {str(e)}")

# ============================================================================
# USER AUTHENTICATION ENDPOINTS
# ============================================================================

class RegisterRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="User role: 'client' or 'admin' (miner/validator roles require API key generation with credentials)")
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ['client', 'admin']:
            raise ValueError("Role must be 'client' or 'admin'. To become a miner/validator, register as client first, then generate API key with credentials.")
        return v

class LoginRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    email: str = Field(..., description="User email address")

class GenerateAPIKeyRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    email: str = Field(..., description="User email address")
    hotkey: Optional[str] = Field(None, description="Bittensor hotkey address (required for miner/validator role upgrade)")
    coldkey_address: Optional[str] = Field(None, description="Bittensor coldkey address (required for miner/validator role upgrade)")
    uid: Optional[int] = Field(None, description="Bittensor UID (required for miner/validator role upgrade)")
    network: Optional[str] = Field(None, description="Network: 'test' or 'finney' (required for miner/validator role upgrade)")
    target_role: Optional[str] = Field(None, description="Target role: 'miner' or 'validator' (optional, for role upgrade)")

class APIKeyResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    success: bool
    api_key: Optional[str] = None
    role: Optional[str] = None
    message: str

@app.post("/api/v1/auth/register", response_model=Dict[str, Any])
async def register_user(request: RegisterRequest):
    """Register a new user with role-based authentication. Only 'client' and 'admin' roles allowed. To become miner/validator, use generate-api-key endpoint."""
    try:
        from database.user_schema import UserOperations
        
        # Validate role - only client or admin allowed during registration
        if request.role not in ['client', 'admin']:
            raise HTTPException(
                status_code=400,
                detail="Registration only allows 'client' or 'admin' roles. To become a miner/validator, register as client first, then generate API key with credentials."
            )
        
        # Check if user already exists
        if UserOperations.verify_user_exists(db_manager, request.email):
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        # Client and admin don't need Bittensor credentials
        user_data = {
            'email': request.email,
            'role': request.role
        }
        
        # Create user
        user_id = UserOperations.create_user(db_manager, user_data)
        user = UserOperations.get_user_by_email(db_manager, request.email)
        
        return {
            "success": True,
            "user_id": user_id,
            "email": user['email'],
            "role": user['role'],
            "api_key": user['api_key'],
            "message": f"User registered successfully as {request.role}. To become a miner/validator, use generate-api-key endpoint with credentials."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Registration error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/v1/auth/login", response_model=Dict[str, Any])
async def login_user(request: LoginRequest):
    """Login user and return API key"""
    try:
        from database.user_schema import UserOperations
        
        user = UserOperations.get_user_by_email(db_manager, request.email)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.get('is_active', True):
            raise HTTPException(status_code=403, detail="User account is inactive")
        
        # Update last login
        UserOperations.update_last_login(db_manager, user['user_id'])
        
        return {
            "success": True,
            "user_id": user['user_id'],
            "email": user['email'],
            "role": user.get('role', 'client'),
            "api_key": user.get('api_key'),
            "uid": user.get('uid'),
            "network": user.get('network'),
            "hotkey": user.get('hotkey'),
            "coldkey_address": user.get('coldkey_address'),
            "message": "Login successful"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {e}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@app.post("/api/v1/auth/generate-api-key", response_model=APIKeyResponse)
async def generate_api_key(request: GenerateAPIKeyRequest):
    """Generate a new API key for user. Can upgrade client to miner/validator by providing credentials."""
    try:
        from database.user_schema import UserOperations
        from utils.bittensor_verifier import BittensorVerifier
        from datetime import datetime
        
        user = UserOperations.get_user_by_email(db_manager, request.email)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.get('is_active', True):
            raise HTTPException(status_code=403, detail="User account is inactive")
        
        current_role = user.get('role', 'client')
        target_role = request.target_role
        
        # If upgrading to miner/validator, verify credentials
        if target_role in ['miner', 'validator']:
            if not all([request.hotkey, request.coldkey_address, request.uid, request.network]):
                raise HTTPException(
                    status_code=400,
                    detail=f"hotkey, coldkey_address, uid, and network are required to upgrade to {target_role} role"
                )
            
            # Determine netuid based on network
            netuid = 292 if request.network == 'test' else 49
            
            # Verify credentials against Bittensor metagraph
            verifier = BittensorVerifier()
            is_valid, error_msg = verifier.verify_credentials(
                hotkey=request.hotkey,
                coldkey_address=request.coldkey_address,
                uid=request.uid,
                network=request.network,
                netuid=netuid
            )
            
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_msg or "Credential verification failed")
            
            # Update user role and credentials
            db = db_manager.get_db()
            user_ref = db.collection('users').document(user['user_id'])
            user_ref.update({
                'role': target_role,
                'hotkey': request.hotkey,
                'coldkey_address': request.coldkey_address,
                'uid': request.uid,
                'network': request.network,
                'netuid': netuid,
                'updated_at': datetime.now()
            })
            
            # Update API key index with new role (will be done in generate_new_api_key)
        
        # Generate new API key (this will update the API key index with current role)
        api_key = UserOperations.generate_new_api_key(db_manager, user['user_id'])
        
        # Get updated user info
        updated_user = UserOperations.get_user_by_email(db_manager, request.email)
        final_role = updated_user.get('role', current_role)
        
        message = f"API key generated successfully"
        if target_role and target_role != current_role:
            message = f"API key generated successfully. User upgraded from {current_role} to {final_role} role."
            if final_role in ['validator', 'miner']:
                key_name = f"{final_role.upper()}_API_KEY"
                message += f" Please manually add {key_name}={api_key} to your .env file."
        
        return {
            "success": True,
            "api_key": api_key,
            "role": final_role,
            "message": message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ API key generation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"API key generation failed: {str(e)}")

@app.get("/api/v1/auth/verify-api-key")
async def verify_api_key(api_key: str = None):
    """Verify if an API key is valid"""
    try:
        from middleware.auth_middleware import AuthMiddleware
        
        if not api_key:
            raise HTTPException(status_code=400, detail="API key is required")
        
        auth_middleware = AuthMiddleware(db_manager.get_db())
        user_info = auth_middleware.verify_api_key(api_key)
        
        return {
            "valid": True,
            "role": user_info.get('role'),
            "user_id": user_info.get('user_id'),
            "email": user_info.get('email'),
            "uid": user_info.get('uid'),
            "network": user_info.get('network'),
            "message": "API key is valid"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ API key verification error: {e}")
        raise HTTPException(status_code=500, detail=f"API key verification failed: {str(e)}")

# ============================================================================
# MINER ENDPOINTS (Protected with miner API key)
# ============================================================================

class MinerAuthRequest(BaseModel):
    """Miner authentication request with credentials"""
    model_config = ConfigDict(protected_namespaces=())
    
    hotkey: str = Field(..., description="Miner hotkey address")
    coldkey_address: str = Field(..., description="Miner coldkey address")
    uid: int = Field(..., description="Miner UID")
    network: str = Field(..., description="Network: 'test' or 'finney'")

@app.post("/api/v1/miner/authenticate")
async def authenticate_miner(
    request: MinerAuthRequest,
    http_request: Request
):
    """Authenticate miner and verify credentials match API key"""
    try:
        from middleware.auth_middleware import AuthMiddleware
        
        # Get API key from header or query
        api_key = http_request.headers.get("X-API-Key") or http_request.query_params.get("api_key")
        
        if not api_key:
            raise HTTPException(status_code=401, detail="API key is required")
        
        auth_middleware = AuthMiddleware(db_manager.get_db())
        user_info = auth_middleware.verify_api_key(api_key)
        
        # Verify miner credentials match
        if not auth_middleware.verify_miner_credentials(
            user_info,
            request.hotkey,
            request.coldkey_address,
            request.uid,
            request.network
        ):
            raise HTTPException(
                status_code=403,
                detail="Miner credentials do not match the provided API key"
            )
        
        return {
            "success": True,
            "authenticated": True,
            "uid": request.uid,
            "network": request.network,
            "message": "Miner authenticated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Miner authentication error: {e}")
        raise HTTPException(status_code=500, detail=f"Miner authentication failed: {str(e)}")

# ============================================================================
# VALIDATOR ENDPOINTS (Protected with validator API key)
# ============================================================================

class ValidatorAuthRequest(BaseModel):
    """Validator authentication request with credentials"""
    model_config = ConfigDict(protected_namespaces=())
    
    hotkey: str = Field(..., description="Validator hotkey address")
    coldkey_address: str = Field(..., description="Validator coldkey address")
    uid: int = Field(..., description="Validator UID")
    network: str = Field(..., description="Network: 'test' or 'finney'")

@app.post("/api/v1/validator/authenticate")
async def authenticate_validator(
    request: ValidatorAuthRequest,
    http_request: Request
):
    """Authenticate validator and verify credentials match API key"""
    try:
        from middleware.auth_middleware import AuthMiddleware
        
        # Get API key from header or query
        api_key = http_request.headers.get("X-API-Key") or http_request.query_params.get("api_key")
        
        if not api_key:
            raise HTTPException(status_code=401, detail="API key is required")
        
        auth_middleware = AuthMiddleware(db_manager.get_db())
        user_info = auth_middleware.verify_api_key(api_key)
        
        # Verify validator credentials match
        if not auth_middleware.verify_validator_credentials(
            user_info,
            request.hotkey,
            request.coldkey_address,
            request.uid,
            request.network
        ):
            raise HTTPException(
                status_code=403,
                detail="Validator credentials do not match the provided API key"
            )
        
        return {
            "success": True,
            "authenticated": True,
            "uid": request.uid,
            "network": request.network,
            "message": "Validator authenticated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Validator authentication error: {e}")
        raise HTTPException(status_code=500, detail=f"Validator authentication failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

