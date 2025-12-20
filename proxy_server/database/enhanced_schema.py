"""
Enhanced Database Schema for Production Task Management
This schema provides comprehensive models for tasks, files, miners, and responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
import uuid
import hashlib
import time

# Enums
class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class TaskType(str, Enum):
    TRANSCRIPTION = "transcription"
    TTS = "tts"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    VIDEO_TRANSCRIPTION = "video_transcription"
    TEXT_TRANSLATION = "text_translation"
    DOCUMENT_TRANSLATION = "document_translation"

class MinerStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"

class ResponseStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

# Core Data Models
@dataclass
class TextContent:
    """Text content for summarization and other text-based tasks"""
    content_id: str
    text: str
    created_at: datetime
    updated_at: datetime
    source_language: str = "en"
    detected_language: Optional[str] = None
    language_confidence: Optional[float] = None
    text_length: int = 0
    word_count: int = 0
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class FileReference:
    """Reference to a file stored in the system"""
    file_id: str
    file_name: str
    file_type: str
    file_size: int
    local_path: str
    file_url: str
    content_type: str
    checksum: str
    created_at: datetime
    updated_at: datetime

@dataclass
class MinerInfo:
    """Information about a miner"""
    uid: int
    hotkey: str
    ip: str
    port: int
    external_ip: Optional[str] = None
    external_port: Optional[int] = None
    is_serving: bool = True
    stake: float = 0.0
    performance_score: float = 0.0
    current_load: float = 0.0
    max_capacity: float = 100.0
    task_type_specialization: Optional[str] = None
    last_seen: Optional[datetime] = None

@dataclass
class TaskAssignment:
    """Assignment of a task to a miner"""
    assignment_id: str
    miner_uid: int
    assigned_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: ResponseStatus = ResponseStatus.PENDING
    processing_time: Optional[float] = None
    accuracy_score: Optional[float] = None
    speed_score: Optional[float] = None
    error_message: Optional[str] = None

@dataclass
class MinerResponse:
    """Response from a miner for a task"""
    response_id: str
    miner_uid: int
    submitted_at: datetime
    processing_time: float
    accuracy_score: float
    speed_score: float
    output_data: Union[str, Dict[str, Any]]
    output_file: Optional[FileReference] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class TaskModel:
    """Complete task model with all related data"""
    task_id: str
    task_type: TaskType
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime
    
    # Input/Output - can be either file-based or text-based
    input_file: Optional[FileReference] = None
    input_text: Optional[TextContent] = None
    output_file: Optional[FileReference] = None
    
    # Task details
    source_language: str = "en"
    target_language: Optional[str] = None
    model_id: Optional[str] = None  # HuggingFace model ID for dynamic model selection
    estimated_completion_time: Optional[float] = None
    actual_completion_time: Optional[float] = None
    deadline: Optional[datetime] = None
    
    # Assignment and execution
    required_miner_count: int = 1
    assigned_miners: List[int] = field(default_factory=list)
    task_assignments: List[TaskAssignment] = field(default_factory=list)
    miner_responses: List[MinerResponse] = field(default_factory=list)
    
    # Results and evaluation
    best_response: Optional[MinerResponse] = None
    evaluation_data: Optional[Dict[str, Any]] = None
    
    # Metadata
    user_metadata: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)
    callback_url: Optional[str] = None
    distributed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None

# Collection names
COLLECTIONS = {
    'tasks': 'tasks',
    'files': 'files',
    'text_content': 'text_content',
    'miners': 'miners',
    'miner_status': 'miner_status',
    'assignments': 'task_assignments',
    'responses': 'miner_responses',
    'evaluations': 'task_evaluations',
    'system_metrics': 'system_metrics',
    'users': 'users',
    'user_emails': 'user_emails'
}

# Required indexes for Firestore
REQUIRED_INDEXES = [
    'tasks_status_created_at',
    'tasks_type_status',
    'tasks_assigned_miners',
    'miner_status_uid_updated_at',
    'assignments_task_id_miner_uid',
    'responses_task_id_miner_uid'
]

# Utility functions
def generate_task_id() -> str:
    """Generate a unique task ID"""
    return str(uuid.uuid4())

def generate_assignment_id() -> str:
    """Generate a unique assignment ID"""
    return str(uuid.uuid4())

def generate_response_id() -> str:
    """Generate a unique response ID"""
    return str(uuid.uuid4())

def generate_file_id() -> str:
    """Generate a unique file ID"""
    return str(uuid.uuid4())

def generate_text_content_id() -> str:
    """Generate a unique text content ID"""
    return str(uuid.uuid4())

def validate_task_data(task_data: Dict[str, Any]) -> bool:
    """Validate task data structure"""
    required_fields = ['task_type', 'priority']
    
    # Must have either input_file or input_text
    has_input = 'input_file' in task_data or 'input_text' in task_data
    
    return all(field in task_data for field in required_fields) and has_input

def calculate_task_score(accuracy: float, speed: float, processing_time: float) -> float:
    """Calculate overall task score"""
    # Weighted combination of accuracy and speed
    accuracy_weight = 0.7
    speed_weight = 0.3
    
    # Normalize processing time (lower is better)
    time_score = max(0.0, min(1.0, 10.0 / max(processing_time, 0.1)))
    
    return (accuracy * accuracy_weight) + (speed * speed_weight) + (time_score * 0.1)

# Database Operations
class DatabaseOperations:
    """Static class for common database operations - supports both PostgreSQL and Firestore"""
    
    @staticmethod
    def _is_postgresql_adapter(db) -> bool:
        """Check if db is a PostgreSQL adapter"""
        from database.postgresql_adapter import PostgreSQLAdapter
        return isinstance(db, PostgreSQLAdapter)
    
    @staticmethod
    def create_task(db, task_data: Dict[str, Any]) -> str:
        """Create a new task in the database"""
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            # Use PostgreSQL adapter
            task_data['created_at'] = datetime.utcnow()
            task_data['updated_at'] = datetime.utcnow()
            
            # Set default values
            if 'status' not in task_data:
                task_data['status'] = TaskStatus.PENDING.value
            if 'priority' not in task_data:
                task_data['priority'] = TaskPriority.NORMAL.value
            if 'required_miner_count' not in task_data:
                task_data['required_miner_count'] = 1
            
            # Convert enums to strings for PostgreSQL
            if isinstance(task_data.get('status'), TaskStatus):
                task_data['status'] = task_data['status'].value
            if isinstance(task_data.get('priority'), TaskPriority):
                task_data['priority'] = task_data['priority'].value
            if isinstance(task_data.get('task_type'), TaskType):
                task_data['task_type'] = task_data['task_type'].value
            
            return db.create_task(task_data)
        
        # Firestore (legacy)
        task_id = generate_task_id()
        task_data['task_id'] = task_id
        task_data['created_at'] = datetime.utcnow()
        task_data['updated_at'] = datetime.utcnow()
        
        # Set default values
        if 'status' not in task_data:
            task_data['status'] = TaskStatus.PENDING
        if 'priority' not in task_data:
            task_data['priority'] = TaskPriority.NORMAL
        if 'required_miner_count' not in task_data:
            task_data['required_miner_count'] = 1
        
        # Create task document
        db.collection(COLLECTIONS['tasks']).document(task_id).set(task_data)
        return task_id
    
    @staticmethod
    def get_miner_task_count(db, miner_uid: int) -> int:
        """Get the number of active tasks currently assigned to a miner"""
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            return db.get_miner_task_count(miner_uid)
        
        # Firestore (legacy)
        try:
            # Count tasks where miner is in assigned_miners and status is not completed/failed
            tasks_ref = db.collection(COLLECTIONS['tasks'])
            
            # Query for tasks with this miner in assigned_miners
            # Note: Firestore doesn't support array-contains with status filter in one query
            # So we'll query all tasks and filter in Python
            active_statuses = ['pending', 'assigned', 'processing']
            task_count = 0
            
            # Get all tasks with this miner assigned
            all_tasks = tasks_ref.where('assigned_miners', 'array_contains', miner_uid).stream()
            
            for task_doc in all_tasks:
                task_data = task_doc.to_dict()
                status = task_data.get('status', 'unknown')
                if status in active_statuses:
                    task_count += 1
            
            return task_count
            
        except Exception as e:
            print(f"⚠️ Error getting miner task count for miner {miner_uid}: {e}")
            return 0
    
    @staticmethod
    def update_miner_task_load(db, miner_uid: int, increment: bool = True):
        """Update miner's task load count in miner_status collection"""
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            db.update_miner_task_load(miner_uid, increment)
            return
        
        # Firestore (legacy)
        try:
            miner_status_ref = db.collection('miner_status').document(str(miner_uid))
            miner_doc = miner_status_ref.get()
            
            if miner_doc.exists:
                miner_data = miner_doc.to_dict()
                current_task_count = miner_data.get('assigned_task_count', 0)
                max_capacity = miner_data.get('max_capacity', 5)
                
                if increment:
                    new_task_count = current_task_count + 1
                else:
                    new_task_count = max(0, current_task_count - 1)
                
                # Update both task count and load
                miner_status_ref.update({
                    'assigned_task_count': new_task_count,
                    'current_load': min(max_capacity, new_task_count),  # Sync with task count
                    'updated_at': datetime.utcnow()
                })
                
                print(f"📊 Updated miner {miner_uid} task load: {current_task_count} → {new_task_count}")
            else:
                # Miner status doesn't exist, create it
                miner_status_ref.set({
                    'uid': miner_uid,
                    'assigned_task_count': 1 if increment else 0,
                    'current_load': 1 if increment else 0,
                    'max_capacity': 5,
                    'updated_at': datetime.utcnow()
                })
                
        except Exception as e:
            print(f"⚠️ Error updating miner task load for miner {miner_uid}: {e}")
    
    @staticmethod
    def assign_task_to_miners(db, task_id: str, miner_uids: List[int], min_count: int = 1, max_count: int = 5) -> bool:
        """
        Assign a task to multiple miners with min/max constraints and duplicate prevention.
        Only assigns new miners that haven't been assigned to this task yet.
        Continues assigning until max_count is reached.
        Tracks global miner load to prevent over-assignment.
        """
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            # For PostgreSQL, we need to enhance the adapter method to handle min/max and capacity checks
            # For now, use the adapter's method and enhance it later if needed
            return db.assign_task_to_miners(task_id, miner_uids, min_count, max_count)
        
        # Firestore (legacy)
        try:
            task_ref = db.collection(COLLECTIONS['tasks']).document(task_id)
            task_doc = task_ref.get()
            
            if not task_doc.exists:
                print(f"❌ Task {task_id} not found")
                return False
            
            task_data = task_doc.to_dict()
            
            # Get currently assigned miners
            current_assigned_miners = task_data.get('assigned_miners', [])
            current_assignments = task_data.get('task_assignments', [])
            
            # Filter out miners already assigned to this task (prevent duplicates)
            new_miner_uids = [uid for uid in miner_uids if uid not in current_assigned_miners]
            
            if not new_miner_uids:
                print(f"⚠️ All requested miners already assigned to task {task_id}")
                current_count = len(current_assigned_miners)
                if current_count < min_count:
                    print(f"   ⚠️ Task has {current_count} miners (below minimum {min_count})")
                elif current_count >= max_count:
                    print(f"   ✅ Task has {current_count} miners (at/above maximum {max_count})")
                else:
                    print(f"   ℹ️ Task has {current_count} miners (between min {min_count} and max {max_count})")
                return False
            
            # Check miner capacity before assigning (global load tracking)
            available_miner_uids = []
            for miner_uid in new_miner_uids:
                # Get miner's current task count
                task_count = DatabaseOperations.get_miner_task_count(db, miner_uid)
                
                # Get miner's max capacity
                miner_status_ref = db.collection('miner_status').document(str(miner_uid))
                miner_doc = miner_status_ref.get()
                if miner_doc.exists:
                    miner_data = miner_doc.to_dict()
                    max_capacity = miner_data.get('max_capacity', 5)
                else:
                    max_capacity = 5  # Default capacity
                
                if task_count < max_capacity:
                    available_miner_uids.append(miner_uid)
                    print(f"   ✅ Miner {miner_uid}: {task_count}/{max_capacity} tasks (available)")
                else:
                    print(f"   ⚠️ Miner {miner_uid}: {task_count}/{max_capacity} tasks (at capacity, skipping)")
            
            if not available_miner_uids:
                print(f"⚠️ All requested miners are at capacity for task {task_id}")
                return False
            
            # Create assignments for available miners only
            new_assignments = []
            for miner_uid in available_miner_uids:
                assignment = {
                    'assignment_id': generate_assignment_id(),
                    'miner_uid': miner_uid,
                    'assigned_at': datetime.utcnow(),
                    'status': ResponseStatus.PENDING
                }
                new_assignments.append(assignment)
                
                # Update miner's global task load
                DatabaseOperations.update_miner_task_load(db, miner_uid, increment=True)
            
            # Combine existing and new assignments
            all_assigned_miners = current_assigned_miners + available_miner_uids
            all_assignments = current_assignments + new_assignments
            
            # Check if we've reached max_count
            final_count = len(all_assigned_miners)
            reached_max = final_count >= max_count
            meets_minimum = final_count >= min_count
            
            # Update task with all assignments
            update_data = {
                'assigned_miners': all_assigned_miners,
                'task_assignments': all_assignments,
                'updated_at': datetime.utcnow(),
                'actual_miner_count': final_count
            }
            
            # Only update status to 'assigned' if we meet minimum requirement
            if meets_minimum:
                update_data['status'] = TaskStatus.ASSIGNED.value
                if 'distributed_at' not in task_data:
                    update_data['distributed_at'] = datetime.utcnow()
            
            task_ref.update(update_data)
            
            print(f"✅ Assigned {len(available_miner_uids)} new miner(s) to task {task_id}")
            print(f"   Total miners: {final_count} (min: {min_count}, max: {max_count})")
            print(f"   New miners: {available_miner_uids}")
            if reached_max:
                print(f"   ✅ Maximum miner count ({max_count}) reached")
            elif not meets_minimum:
                print(f"   ⚠️ Below minimum ({min_count}), need {min_count - final_count} more miner(s)")
            else:
                print(f"   ℹ️ Can assign {max_count - final_count} more miner(s) to reach maximum")
            
            return True
        except Exception as e:
            print(f"❌ Error assigning task to miners: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def get_tasks_by_status(db, status: TaskStatus, limit: int = 100) -> List[Dict[str, Any]]:
        """Get tasks by status"""
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            # Normalize status to string
            status_str = status.value if isinstance(status, TaskStatus) else status
            return db.get_tasks_by_status(status_str, limit)
        
        # Firestore (legacy)
        try:
            # Normalize status to string if it's an enum
            status_str = status.value if isinstance(status, TaskStatus) else status
            
            query = db.collection(COLLECTIONS['tasks']).where('status', '==', status_str).limit(limit)
            docs = query.stream()
            tasks = []
            for doc in docs:
                task_data = doc.to_dict()
                task_data['task_id'] = doc.id  # CRITICAL: Add task_id from document ID
                tasks.append(task_data)
            return tasks
        except Exception as e:
            print(f"❌ Error getting tasks by status: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def get_task(db, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID"""
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            return db.get_task(task_id)
        
        # Firestore (legacy)
        try:
            doc = db.collection(COLLECTIONS['tasks']).document(task_id).get()
            if doc.exists:
                task_data = doc.to_dict()
                task_data['task_id'] = doc.id  # CRITICAL: Add task_id from document ID
                return task_data
            else:
                return None
        except Exception as e:
            print(f"❌ Error getting task {task_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def get_miner_tasks(db, miner_uid: int, status: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        """Get tasks assigned to a specific miner with proper status filtering"""
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            from sqlalchemy import and_, or_, func
            from database.postgresql_schema import Task, TaskStatusEnum
            session = db._get_session()
            try:
                # Normalize status - handle string input from query parameter
                if status:
                    if isinstance(status, str):
                        # Map common status strings to enum values
                        status_mapping = {
                            "assigned": TaskStatusEnum.ASSIGNED,
                            "pending": TaskStatusEnum.PENDING,
                            "processing": TaskStatusEnum.IN_PROGRESS,  # Map "processing" to "in_progress"
                            "in_progress": TaskStatusEnum.IN_PROGRESS,
                            "completed": TaskStatusEnum.COMPLETED,
                            "failed": TaskStatusEnum.FAILED,
                            "cancelled": TaskStatusEnum.CANCELLED,
                            "approved": TaskStatusEnum.APPROVED
                        }
                        
                        # Try mapping first
                        if status.lower() in status_mapping:
                            status_enum = status_mapping[status.lower()]
                        else:
                            # Try direct enum lookup
                            try:
                                status_enum = TaskStatusEnum[status.upper()]
                            except (KeyError, AttributeError):
                                # Fallback: try to match by value
                                status_enum = TaskStatusEnum(status)
                    elif isinstance(status, TaskStatus):
                        status_enum = TaskStatusEnum(status.value)
                    else:
                        status_enum = TaskStatusEnum(status)
                else:
                    status_enum = TaskStatusEnum.ASSIGNED
                
                # Query tasks assigned to this miner using PostgreSQL array containment
                # Use PostgreSQL-specific @> operator (contains) for array containment check
                from sqlalchemy.dialects.postgresql import array
                from sqlalchemy import literal
                # Use PostgreSQL array containment operator: array @> [value]
                query = session.query(Task).filter(
                    Task.assigned_miners.op('@>')(array([miner_uid]))
                )
                
                # Filter by status
                if status:
                    # Include both requested status and pending (for tasks in transition)
                    if status_enum == TaskStatusEnum.ASSIGNED:
                        query = query.filter(
                            or_(
                                Task.status == TaskStatusEnum.ASSIGNED,
                                Task.status == TaskStatusEnum.PENDING
                            )
                        )
                    else:
                        query = query.filter(Task.status == status_enum)
                
                # Note: We don't use distinct() here because it conflicts with JSON columns
                # Duplicates are handled in Python code below
                tasks = query.all()
                result = [db._task_to_dict(task) for task in tasks]
                
                # Remove duplicates
                seen_ids = set()
                unique_tasks = []
                for task in result:
                    if task['task_id'] not in seen_ids:
                        seen_ids.add(task['task_id'])
                        unique_tasks.append(task)
                
                print(f"🔍 Found {len(unique_tasks)} tasks for miner {miner_uid}")
                return unique_tasks
            finally:
                session.close()
        
        # Firestore (legacy)
        try:
            # Normalize status to string if it's an enum
            status_str = status.value if isinstance(status, TaskStatus) else (status or 'assigned')
            
            # Query for tasks with the specified status OR pending (in case assignment is in progress)
            # This ensures miners get tasks even if status update is delayed
            query = db.collection(COLLECTIONS['tasks'])
            
            # Query for both 'assigned' and 'pending' status to catch tasks in transition
            # Firestore doesn't support OR queries directly, so we'll query separately and merge
            tasks = []
            
            # Query 1: Get tasks with the requested status
            status_query = query.where('status', '==', status_str)
            docs = status_query.stream()
            
            for doc in docs:
                task_data = doc.to_dict()
                task_data['task_id'] = doc.id  # CRITICAL: Add task_id from document ID
                
                # Only include tasks assigned to this specific miner
                assigned_miners = task_data.get('assigned_miners', [])
                if miner_uid in assigned_miners:
                    tasks.append(task_data)
            
            # Query 2: Also check for 'pending' tasks if status was 'assigned' (to catch tasks being assigned)
            if status_str == 'assigned':
                pending_query = query.where('status', '==', 'pending')
                pending_docs = pending_query.stream()
                
                for doc in pending_docs:
                    task_data = doc.to_dict()
                    task_data['task_id'] = doc.id
                    
                    # Check if this pending task is assigned to this miner
                    assigned_miners = task_data.get('assigned_miners', [])
                    if miner_uid in assigned_miners:
                        # Only add if not already in tasks list (avoid duplicates)
                        if not any(t.get('task_id') == doc.id for t in tasks):
                            tasks.append(task_data)
            
            print(f"🔍 Found {len(tasks)} tasks for miner {miner_uid} with status '{status_str}' (including pending if applicable)")
            return tasks
            
        except Exception as e:
            print(f"❌ Error getting miner tasks for miner {miner_uid}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def update_task_status(db, task_id: str, status: TaskStatus, **kwargs) -> bool:
        """Update task status and other fields. Also updates miner load when task completes/fails."""
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            update_data = {
                'status': status.value if isinstance(status, TaskStatus) else status,
                'updated_at': datetime.utcnow()
            }
            update_data.update(kwargs)
            
            # If task is being marked as completed or failed, decrement miner load
            status_str = status.value if isinstance(status, TaskStatus) else status
            if status_str in ['completed', 'failed', 'cancelled']:
                # Get task to find assigned miners
                task = db.get_task(task_id)
                if task:
                    assigned_miners = task.get('assigned_miners', [])
                    
                    # Decrement load for all assigned miners
                    for miner_uid in assigned_miners:
                        DatabaseOperations.update_miner_task_load(db, miner_uid, increment=False)
                        print(f"📉 Decremented miner {miner_uid} load (task {task_id} {status_str})")
            
            return db.update_task(task_id, update_data)
        
        # Firestore (legacy)
        try:
            update_data = {
                'status': status.value if isinstance(status, TaskStatus) else status,
                'updated_at': datetime.utcnow()
            }
            update_data.update(kwargs)
            
            # If task is being marked as completed or failed, decrement miner load
            status_str = status.value if isinstance(status, TaskStatus) else status
            if status_str in ['completed', 'failed', 'cancelled']:
                # Get task to find assigned miners
                task_ref = db.collection(COLLECTIONS['tasks']).document(task_id)
                task_doc = task_ref.get()
                
                if task_doc.exists:
                    task_data = task_doc.to_dict()
                    assigned_miners = task_data.get('assigned_miners', [])
                    
                    # Decrement load for all assigned miners
                    for miner_uid in assigned_miners:
                        DatabaseOperations.update_miner_task_load(db, miner_uid, increment=False)
                        print(f"📉 Decremented miner {miner_uid} load (task {task_id} {status_str})")
            
            db.collection(COLLECTIONS['tasks']).document(task_id).update(update_data)
            return True
        except Exception as e:
            print(f"❌ Error updating task status: {e}")
            return False
    
    @staticmethod
    def get_all_miners(db) -> List[Dict[str, Any]]:
        """Get all registered miners"""
        try:
            query = db.collection(COLLECTIONS['miners'])
            docs = query.stream()
            miners = []
            
            for doc in docs:
                miner_data = doc.to_dict()
                miner_data['id'] = doc.id
                miners.append(miner_data)
            
            print(f"🔍 Found {len(miners)} total miners")
            return miners
            
        except Exception as e:
            print(f"❌ Error getting all miners: {e}")
            return []
    
    @staticmethod
    def register_miner(db, miner_data: Dict[str, Any]) -> bool:
        """Register or update a miner in the database"""
        try:
            miner_uid = miner_data.get('uid')
            if not miner_uid:
                print("❌ Cannot register miner without UID")
                return False
            
            # Set default values
            miner_data['updated_at'] = datetime.utcnow()
            if 'registered_at' not in miner_data:
                miner_data['registered_at'] = datetime.utcnow()
            if 'last_seen' not in miner_data:
                miner_data['last_seen'] = datetime.utcnow()
            
            # Store in miners collection
            db.collection(COLLECTIONS['miners']).document(str(miner_uid)).set(miner_data, merge=True)
            
            print(f"✅ Miner {miner_uid} registered/updated successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error registering miner: {e}")
            return False

    @staticmethod
    def get_available_miners(db, task_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get available miners that can process tasks - dynamically queries miner_status collection"""
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            return db.get_available_miners(task_type, limit)
        
        # Firestore (legacy)
        try:
            # Use miner_status collection (populated by validators) for dynamic miner selection
            query = db.collection(COLLECTIONS.get('miner_status', 'miner_status'))
            
            # Filter by availability - must be serving
            query = query.where('is_serving', '==', True)
            
            # Get all serving miners first, then filter in Python for better control
            docs = query.stream()
            miners = []
            current_time = datetime.utcnow()
            miner_timeout = 900  # 15 minutes
            
            for doc in docs:
                miner_data = doc.to_dict()
                
                # Check if miner is recently seen (within timeout)
                last_seen = miner_data.get('last_seen')
                if last_seen:
                    try:
                        # Handle different timestamp formats
                        if isinstance(last_seen, datetime):
                            time_diff = (current_time - last_seen).total_seconds()
                        elif hasattr(last_seen, 'timestamp'):  # Firestore Timestamp
                            time_diff = (current_time.timestamp() - last_seen.timestamp())
                        elif isinstance(last_seen, str):
                            # Parse ISO format string
                            from dateutil import parser
                            last_seen_dt = parser.parse(last_seen)
                            time_diff = (current_time - last_seen_dt.replace(tzinfo=None)).total_seconds()
                        else:
                            # Unknown format, skip this miner
                            print(f"⚠️  Unknown last_seen format for miner {miner_data.get('uid')}: {type(last_seen)}")
                            continue
                        
                        # Skip miners that haven't been seen recently (stale miners)
                        if time_diff > miner_timeout:
                            print(f"⏰ Skipping stale miner {miner_data.get('uid')} - last seen {time_diff/60:.1f} minutes ago")
                            continue
                    except Exception as e:
                        print(f"⚠️  Error checking last_seen for miner {miner_data.get('uid')}: {e}")
                        continue
                else:
                    # No last_seen timestamp - skip this miner (too old or invalid)
                    print(f"⚠️  Miner {miner_data.get('uid')} has no last_seen timestamp - skipping")
                    continue
                
                # Check miner capacity using both current_load and assigned_task_count
                current_load = miner_data.get('current_load', 0)
                assigned_task_count = miner_data.get('assigned_task_count', 0)
                max_capacity = miner_data.get('max_capacity', 5)
                
                # Use the higher of the two (most conservative)
                effective_load = max(current_load, assigned_task_count)
                
                if effective_load >= max_capacity:
                    print(f"⏸️ Skipping miner {miner_data.get('uid')} - at capacity (load: {effective_load}/{max_capacity})")
                    continue  # Skip overloaded miners
                
                # Check task type specialization if specified
                if task_type:
                    specialization = miner_data.get('task_type_specialization')
                    if specialization and task_type not in specialization:
                        continue  # Skip miners that don't support this task type
                
                # Calculate availability score for sorting
                performance_score = miner_data.get('performance_score', 0.5)
                load_factor = 1.0 - (current_load / max_capacity)
                stake = miner_data.get('stake', 0.0)
                stake_factor = min(1.0, stake / 1000.0)
                
                availability_score = (performance_score * 0.4 + load_factor * 0.3 + stake_factor * 0.2)
                
                miners.append({
                    **miner_data,
                    'availability_score': availability_score
                })
            
            # Sort by availability score (higher is better)
            miners.sort(key=lambda x: x.get('availability_score', 0), reverse=True)
            
            # Return top miners up to limit
            selected_miners = miners[:limit]
            
            print(f"🔍 Found {len(selected_miners)} available miners (from {len(miners)} total) for task type '{task_type or 'any'}'")
            return selected_miners
            
        except Exception as e:
            print(f"❌ Error getting available miners: {e}")
            return []
    
    @staticmethod
    def auto_assign_task(db, task_id: str, task_type: str, required_count: int = 3, min_count: int = 1, max_count: int = None) -> bool:
        """Automatically assign a task to available miners with min/max constraints"""
        try:
            # Use required_count as max if max_count not provided
            if max_count is None:
                max_count = required_count
            
            # Get task to check current assignments
            task = DatabaseOperations.get_task(db, task_id)
            if not task:
                print(f"❌ Task {task_id} not found")
                return False
            
            current_assigned = task.get('assigned_miners', [])
            current_count = len(current_assigned)
            
            # Check if we need more miners
            if current_count >= max_count:
                print(f"✅ Task {task_id} already has {current_count} miners (at/above maximum {max_count})")
                return True
            
            # Calculate how many more we need
            needed_count = max_count - current_count
            
            # Ensure we meet minimum
            if current_count < min_count:
                needed_count = max(needed_count, min_count - current_count)
            
            # Get available miners, excluding already assigned ones
            available_miners = DatabaseOperations.get_available_miners(db, task_type, limit=needed_count * 2)
            
            # Filter out already assigned miners
            new_miners = [m for m in available_miners if m.get('uid') not in current_assigned]
            
            if not new_miners:
                print(f"⚠️ No new available miners found for task {task_id} (all already assigned or none available)")
                return False
            
            # Select only what we need
            selected_miners = new_miners[:needed_count]
            miner_uids = [miner['uid'] for miner in selected_miners]
            
            print(f"🎯 Auto-assigning task {task_id}: adding {len(miner_uids)} new miner(s) (current: {current_count}, target: {max_count})")
            
            # Assign the task with min/max constraints
            success = DatabaseOperations.assign_task_to_miners(db, task_id, miner_uids, min_count=min_count, max_count=max_count)
            
            if success:
                print(f"✅ Successfully auto-assigned task {task_id}")
            else:
                print(f"❌ Failed to auto-assign task {task_id}")
            
            return success
            
        except Exception as e:
            print(f"❌ Error auto-assigning task {task_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def add_miner_response(db, task_id: str, miner_uid: int, response_data: Dict[str, Any]) -> bool:
        """Add a miner response to a task"""
        # Check if using PostgreSQL adapter
        if DatabaseOperations._is_postgresql_adapter(db):
            response_id = generate_response_id()
            response = {
                'response_id': response_id,
                'miner_uid': miner_uid,
                'submitted_at': datetime.utcnow().isoformat(),
                **response_data
            }
            
            # Get current task
            task = db.get_task(task_id)
            if not task:
                print(f"❌ Task {task_id} not found")
                return False
            
            miner_responses = task.get('miner_responses', [])
            miner_responses.append(response)
            
            # Update task
            return db.update_task(task_id, {
                'miner_responses': miner_responses,
                'updated_at': datetime.utcnow()
            })
        
        # Firestore (legacy)
        try:
            response_id = generate_response_id()
            response = {
                'response_id': response_id,
                'miner_uid': miner_uid,
                'submitted_at': datetime.utcnow(),
                **response_data
            }
            
            # Get current task
            task_ref = db.collection(COLLECTIONS['tasks']).document(task_id)
            task_doc = task_ref.get()
            
            if not task_doc.exists:
                print(f"❌ Task {task_id} not found")
                return False
            
            task_data = task_doc.to_dict()
            miner_responses = task_data.get('miner_responses', [])
            miner_responses.append(response)
            
            # Update task
            task_ref.update({
                'miner_responses': miner_responses,
                'updated_at': datetime.utcnow()
            })
            
            return True
        except Exception as e:
            print(f"❌ Error adding miner response: {e}")
            return False
