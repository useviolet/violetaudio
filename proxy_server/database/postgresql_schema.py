"""
PostgreSQL Database Schema for Proxy Server
SQLAlchemy models for migrating from Firestore to PostgreSQL
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, Boolean, 
    DateTime, ForeignKey, JSON, Index, Enum as SQLEnum, ARRAY
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum
import uuid

Base = declarative_base()

# Enums matching Firestore schema
class TaskStatusEnum(str, enum.Enum):
    """Simplified task status flow:
    pending -> assigned -> completed -> done (set by validators)
    """
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"  # Optional, can skip
    COMPLETED = "completed"  # All miners responded, ready for validators
    DONE = "done"  # Validators evaluated and rewarded (set by validators)
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriorityEnum(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class TaskTypeEnum(str, enum.Enum):
    TRANSCRIPTION = "transcription"
    TTS = "tts"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    VIDEO_TRANSCRIPTION = "video_transcription"
    TEXT_TRANSLATION = "text_translation"
    DOCUMENT_TRANSLATION = "document_translation"

class ResponseStatusEnum(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

class UserRoleEnum(str, enum.Enum):
    CLIENT = "client"
    MINER = "miner"
    VALIDATOR = "validator"
    ADMIN = "admin"

# Tables
class Task(Base):
    """Tasks table - main task management"""
    __tablename__ = 'tasks'
    
    task_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(SQLEnum(TaskTypeEnum), nullable=False, index=True)
    status = Column(SQLEnum(TaskStatusEnum), nullable=False, default=TaskStatusEnum.PENDING, index=True)
    priority = Column(SQLEnum(TaskPriorityEnum), nullable=False, default=TaskPriorityEnum.NORMAL)
    
    # Input data
    input_file_id = Column(UUID(as_uuid=False), ForeignKey('files.file_id'), nullable=True)
    input_text_id = Column(UUID(as_uuid=False), ForeignKey('text_content.content_id'), nullable=True)
    
    # Language settings
    source_language = Column(String(10), default='en')
    target_language = Column(String(10), nullable=True)
    
    # Task configuration
    model_id = Column(String(255), nullable=True)
    voice_name = Column(String(100), nullable=True)
    speaker_wav_url = Column(Text, nullable=True)
    required_miner_count = Column(Integer, default=3)
    min_miner_count = Column(Integer, default=1)
    max_miner_count = Column(Integer, default=5)
    actual_miner_count = Column(Integer, default=0)
    
    # Assignment tracking
    assigned_miners = Column(ARRAY(Integer), default=[], index=True)
    
    # User and metadata
    user_id = Column(UUID(as_uuid=False), ForeignKey('users.user_id'), nullable=True)
    callback_url = Column(Text, nullable=True)
    user_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    distributed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    all_miners_completed_at = Column(DateTime, nullable=True)
    
    # Results
    miner_responses = Column(JSON, default=list)
    best_response = Column(JSON, nullable=True)
    evaluation_data = Column(JSON, nullable=True)
    
    # Validator tracking (for preventing duplicate rewards)
    validators_seen = Column(JSON, default=list, nullable=True)  # List of validator identifiers that have seen this task
    validators_seen_timestamps = Column(JSON, default=dict, nullable=True)  # Dict mapping validator_identifier to timestamp
    
    # Validator tracking - prevent duplicate rewards
    validators_seen = Column(JSON, default=list)  # List of validator UIDs/identifiers that have seen/rewarded this task
    validators_seen_timestamps = Column(JSON, default=dict)  # Map of validator_uid -> timestamp when seen
    
    # Relationships
    file = relationship("File", foreign_keys=[input_file_id])
    text_content = relationship("TextContent", foreign_keys=[input_text_id])
    user = relationship("User", foreign_keys=[user_id])
    assignments = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_tasks_status_created', 'status', 'created_at'),
        Index('idx_tasks_type_status', 'task_type', 'status'),
        Index('idx_tasks_user_created', 'user_id', 'created_at'),
    )

class TaskAssignment(Base):
    """Task assignments to miners"""
    __tablename__ = 'task_assignments'
    
    assignment_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(UUID(as_uuid=False), ForeignKey('tasks.task_id'), nullable=False, index=True)
    miner_uid = Column(Integer, nullable=False, index=True)
    status = Column(SQLEnum(ResponseStatusEnum), default=ResponseStatusEnum.PENDING)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    task = relationship("Task", back_populates="assignments")
    
    # Indexes
    __table_args__ = (
        Index('idx_assignments_task_miner', 'task_id', 'miner_uid'),
    )

class File(Base):
    """Files stored in R2 or other storage"""
    __tablename__ = 'files'
    
    file_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String(500), nullable=False)
    safe_filename = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String(100), nullable=True)
    file_type = Column(String(50), nullable=True)  # audio, video, document, etc.
    
    # Storage information
    storage_location = Column(String(50), default='r2')  # r2, database, local
    r2_bucket = Column(String(255), nullable=True)
    r2_key = Column(Text, nullable=True)
    public_url = Column(Text, nullable=True)
    file_hash = Column(String(64), nullable=True)  # SHA256
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_files_storage_location', 'storage_location'),
        Index('idx_files_file_type', 'file_type'),
    )

class TextContent(Base):
    """Text content for text-based tasks"""
    __tablename__ = 'text_content'
    
    content_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    text = Column(Text, nullable=False)
    source_language = Column(String(10), default='en')
    detected_language = Column(String(10), nullable=True)
    language_confidence = Column(Float, nullable=True)
    text_length = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    meta_data = Column(JSON, nullable=True)  # Renamed from 'metadata' (reserved in SQLAlchemy)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Miner(Base):
    """Miner information"""
    __tablename__ = 'miners'
    
    uid = Column(Integer, primary_key=True)
    hotkey = Column(String(255), nullable=True)
    ip = Column(String(45), nullable=True)  # IPv6 compatible
    port = Column(Integer, nullable=True)
    external_ip = Column(String(45), nullable=True)
    external_port = Column(Integer, nullable=True)
    
    # Timestamps
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, nullable=True)

class MinerStatus(Base):
    """Current status of miners (updated by validators)"""
    __tablename__ = 'miner_status'
    
    uid = Column(Integer, primary_key=True)
    is_serving = Column(Boolean, default=True, index=True)
    stake = Column(Float, default=0.0)
    performance_score = Column(Float, default=0.0)
    current_load = Column(Float, default=0.0)
    assigned_task_count = Column(Integer, default=0)  # Global task count
    max_capacity = Column(Float, default=5.0)
    task_type_specialization = Column(ARRAY(String), nullable=True)
    availability_score = Column(Float, default=0.5)
    
    # Timestamps
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_miner_status_serving_seen', 'is_serving', 'last_seen'),
    )

class MinerMetrics(Base):
    """
    Miner metrics for reward calculation (uptime, invocation, diversity, bounty).
    
    IMPORTANT: Tracks hotkey+uid combination to handle UID reuse scenarios.
    When a miner is deregistered and another miner gets the same UID, we track
    them as separate entities using hotkey+uid combination.
    """
    __tablename__ = 'miner_metrics'
    
    # Primary key: uid (for backward compatibility)
    uid = Column(Integer, primary_key=True)
    
    # CRITICAL: Track hotkey to handle UID reuse scenarios
    # When UID is reused, we can distinguish between old and new miner
    hotkey = Column(String(255), nullable=False, index=True)
    coldkey = Column(String(255), nullable=True, index=True)
    
    # Unique identifier: hotkey+uid combination (handles UID reuse)
    # This ensures metrics are tracked per miner identity, not just UID
    miner_identity = Column(String(500), nullable=False, unique=True, index=True)  # Format: "{hotkey}_{uid}"
    
    # Timestamp tracking for UID reuse detection
    uid_assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When this UID was assigned to this hotkey
    last_uid_verification = Column(DateTime, default=datetime.utcnow, nullable=False)  # Last time we verified UID still belongs to this hotkey
    
    # Reward components (55% uptime, 25% invocation, 15% diversity, 5% bounty)
    uptime_score = Column(Float, default=0.0)  # 55% weight - percentage of time miner is available
    uptime_percentage = Column(Float, default=0.0)  # Actual uptime percentage
    uptime_seconds = Column(Float, default=0.0)  # Total uptime in seconds
    total_uptime_periods = Column(Integer, default=0)  # Number of uptime measurement periods
    
    invocation_count = Column(Integer, default=0)  # 25% weight - successful user inference requests
    invocation_score = Column(Float, default=0.0)  # Normalized invocation score
    
    diversity_count = Column(Integer, default=0)  # 15% weight - number of unique models/tasks served
    diversity_tasks = Column(JSON, default=list)  # List of unique task types served
    diversity_models = Column(JSON, default=list)  # List of unique models used
    diversity_score = Column(Float, default=0.0)  # Normalized diversity score
    
    bounty_count = Column(Integer, default=0)  # 5% weight - cold-start or priority task completions
    bounty_score = Column(Float, default=0.0)  # Normalized bounty score
    
    # Response speed tracking (for ranking)
    total_response_time = Column(Float, default=0.0)  # Sum of all response times
    response_count = Column(Integer, default=0)  # Number of responses
    average_response_time = Column(Float, default=0.0)  # Average response time
    
    # Timestamps
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_miner_metrics_uid', 'uid'),
        Index('idx_miner_metrics_hotkey', 'hotkey'),
        Index('idx_miner_metrics_identity', 'miner_identity'),
        Index('idx_miner_metrics_uptime', 'uptime_score'),
        Index('idx_miner_metrics_invocation', 'invocation_score'),
    )

class User(Base):
    """User accounts"""
    __tablename__ = 'users'
    
    user_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(SQLEnum(UserRoleEnum), nullable=False, default=UserRoleEnum.CLIENT, index=True)
    api_key = Column(String(255), unique=True, nullable=False, index=True)
    api_key_created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Miner/Validator specific
    hotkey = Column(String(255), nullable=True)
    coldkey_address = Column(String(255), nullable=True)
    uid = Column(Integer, nullable=True, index=True)
    network = Column(String(50), nullable=True)
    netuid = Column(Integer, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

class ValidatorReport(Base):
    """Validator reports for miners"""
    __tablename__ = 'validator_reports'
    
    report_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    validator_uid = Column(Integer, nullable=False, index=True)
    miner_uid = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    epoch = Column(Integer, nullable=False)
    miner_status = Column(JSON, nullable=False)  # Full miner status dict
    confidence_score = Column(Float, default=1.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_validator_report_miner_time', 'miner_uid', 'timestamp'),
        Index('idx_validator_report_validator_time', 'validator_uid', 'timestamp'),
    )

class MinerConsensus(Base):
    """Consensus status for miners based on multiple validator reports"""
    __tablename__ = 'miner_consensus'
    
    miner_uid = Column(Integer, primary_key=True)
    hotkey = Column(String(255), nullable=True)
    consensus_status = Column(JSON, nullable=False)  # Full consensus status dict
    consensus_confidence = Column(Float, default=0.0, index=True)
    validator_reports_count = Column(Integer, default=0)
    conflicting_reports = Column(JSON, default=list)  # List of (validator_uid, conflict_type) tuples
    
    # Timestamps
    last_consensus = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_miner_consensus_confidence', 'consensus_confidence'),
        Index('idx_miner_consensus_time', 'last_consensus'),
    )

class Voice(Base):
    """TTS voices mapping"""
    __tablename__ = 'voices'
    
    voice_name = Column(String(100), primary_key=True)
    display_name = Column(String(255), nullable=False)
    language = Column(String(10), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=False), ForeignKey('files.file_id'), nullable=True)
    r2_key = Column(Text, nullable=True)
    public_url = Column(Text, nullable=False)
    file_name = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(50), default='audio/wav')
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class SystemMetrics(Base):
    """System metrics and statistics"""
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_data = Column(JSON, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_metrics_name_recorded', 'metric_name', 'recorded_at'),
    )

