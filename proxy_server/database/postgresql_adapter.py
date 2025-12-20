"""
PostgreSQL Database Adapter
Implements DatabaseAdapter interface for PostgreSQL using SQLAlchemy
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import create_engine, and_, or_, func, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import os
import uuid
from enum import Enum
import json
import json

from .postgresql_schema import (
    Base, Task, TaskAssignment, File, TextContent, Miner, MinerStatus,
    User, Voice, SystemMetrics, ValidatorReport, MinerConsensus,
    TaskStatusEnum, TaskPriorityEnum, TaskTypeEnum, ResponseStatusEnum
)

class PostgreSQLAdapter:
    """PostgreSQL database adapter implementing DatabaseAdapter interface"""
    
    def __init__(self, database_url: str = None):
        """
        Initialize PostgreSQL adapter
        
        Args:
            database_url: PostgreSQL connection URL
                Format: postgresql://user:password@host:port/database
        """
        if database_url is None:
            # Get from environment variables
            database_url = os.getenv(
                'DATABASE_URL',
                'postgresql://user:password@localhost:5432/violet_proxy'
            )
        
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=10,
            max_overflow=20,
            echo=False  # Set to True for SQL debugging
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
        
        print(f"✅ PostgreSQL adapter initialized")
        print(f"   Database: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    def _get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def get_db(self):
        """Compatibility method - returns self for backward compatibility with Firestore code"""
        return self
    
    def create_task(self, task_data: Dict[str, Any]) -> str:
        """Create a new task"""
        session = self._get_session()
        try:
            # Generate task_id if not provided
            task_id = task_data.get('task_id') or str(uuid.uuid4())
            
            # Convert enums
            task_type = TaskTypeEnum(task_data.get('task_type', 'transcription'))
            status = TaskStatusEnum(task_data.get('status', 'pending'))
            priority = TaskPriorityEnum(task_data.get('priority', 'normal'))
            
            # Create task
            task = Task(
                task_id=task_id,
                task_type=task_type,
                status=status,
                priority=priority,
                source_language=task_data.get('source_language', 'en'),
                target_language=task_data.get('target_language'),
                model_id=task_data.get('model_id'),
                voice_name=task_data.get('voice_name'),
                speaker_wav_url=task_data.get('speaker_wav_url'),
                required_miner_count=task_data.get('required_miner_count', 3),
                min_miner_count=task_data.get('min_miner_count', 1),
                max_miner_count=task_data.get('max_miner_count', 5),
                user_id=task_data.get('user_id'),
                callback_url=task_data.get('callback_url'),
                user_metadata=task_data.get('user_metadata'),
                created_at=task_data.get('created_at', datetime.utcnow()),
                updated_at=datetime.utcnow()
            )
            
            # Handle input_file
            if 'input_file' in task_data and task_data['input_file']:
                input_file = task_data['input_file']
                file_id = input_file.get('file_id')
                if file_id:
                    task.input_file_id = file_id
            
            # Handle input_text
            if 'input_text' in task_data and task_data['input_text']:
                input_text = task_data['input_text']
                if isinstance(input_text, dict):
                    content_id = input_text.get('content_id')
                    if content_id:
                        # Check if text_content exists, if not create it
                        existing_text = session.query(TextContent).filter(TextContent.content_id == content_id).first()
                        if existing_text:
                            task.input_text_id = content_id
                        else:
                            # Create text_content with the provided content_id
                            text_content = TextContent(
                                content_id=content_id,
                                text=input_text.get('text', ''),
                                source_language=input_text.get('source_language', 'en'),
                                detected_language=input_text.get('detected_language'),
                                language_confidence=input_text.get('language_confidence'),
                                text_length=input_text.get('text_length', 0),
                                word_count=input_text.get('word_count', 0),
                                metadata=input_text.get('metadata')
                            )
                            session.add(text_content)
                            task.input_text_id = text_content.content_id
                    else:
                        # Create text_content if content_id not provided
                        text_content = TextContent(
                            content_id=str(uuid.uuid4()),
                            text=input_text.get('text', ''),
                            source_language=input_text.get('source_language', 'en'),
                            detected_language=input_text.get('detected_language'),
                            language_confidence=input_text.get('language_confidence'),
                            text_length=input_text.get('text_length', 0),
                            word_count=input_text.get('word_count', 0),
                            metadata=input_text.get('metadata')
                        )
                        session.add(text_content)
                        task.input_text_id = text_content.content_id
            
            session.add(task)
            session.commit()
            
            print(f"✅ Task created in PostgreSQL: {task_id}")
            return task_id
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"❌ Error creating task in PostgreSQL: {e}")
            raise
        finally:
            session.close()
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID"""
        session = self._get_session()
        try:
            task = session.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                return None
            
            return self._task_to_dict(task, session)
            
        except SQLAlchemyError as e:
            print(f"❌ Error getting task from PostgreSQL: {e}")
            return None
        finally:
            session.close()
    
    def update_task(self, task_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a task"""
        session = self._get_session()
        try:
            task = session.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                print(f"❌ Task {task_id} not found in PostgreSQL")
                return False
            
            # Serialize datetime objects in JSON fields before updating
            update_data = self._serialize_datetime_for_json(update_data)
            
            # Update fields
            for key, value in update_data.items():
                if hasattr(task, key):
                    # Handle enum conversions
                    if key == 'status' and isinstance(value, str):
                        value = TaskStatusEnum(value)
                    elif key == 'priority' and isinstance(value, str):
                        value = TaskPriorityEnum(value)
                    elif key == 'task_type' and isinstance(value, str):
                        value = TaskTypeEnum(value)
                    
                    setattr(task, key, value)
            
            task.updated_at = datetime.utcnow()
            session.commit()
            
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"❌ Error updating task in PostgreSQL: {e}")
            return False
        finally:
            session.close()
    
    def _serialize_datetime_for_json(self, data: Any) -> Any:
        """Recursively serialize datetime objects to ISO format strings for JSON storage"""
        if isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, dict):
            return {key: self._serialize_datetime_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._serialize_datetime_for_json(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(self._serialize_datetime_for_json(item) for item in data)
        else:
            return data
    
    def get_tasks_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get tasks by status"""
        session = self._get_session()
        try:
            status_enum = TaskStatusEnum(status)
            tasks = session.query(Task).filter(
                Task.status == status_enum
            ).order_by(Task.created_at.desc()).limit(limit).all()
            
            return [self._task_to_dict(task, session) for task in tasks]
            
        except SQLAlchemyError as e:
            print(f"❌ Error getting tasks by status from PostgreSQL: {e}")
            return []
        finally:
            session.close()
    
    def assign_task_to_miners(self, task_id: str, miner_uids: List[int], 
                             min_count: int = 1, max_count: int = 5) -> bool:
        """Assign task to miners"""
        session = self._get_session()
        try:
            task = session.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                print(f"❌ Task {task_id} not found in PostgreSQL")
                return False
            
            # Get currently assigned miners
            current_assigned = set(task.assigned_miners or [])
            
            # Filter out already assigned miners
            new_miner_uids = [uid for uid in miner_uids if uid not in current_assigned]
            
            if not new_miner_uids:
                print(f"⚠️ All requested miners already assigned to task {task_id}")
                return False
            
            # Create assignments
            for miner_uid in new_miner_uids:
                assignment = TaskAssignment(
                    task_id=task_id,
                    miner_uid=miner_uid,
                    status=ResponseStatusEnum.PENDING,
                    assigned_at=datetime.utcnow()
                )
                session.add(assignment)
            
            # Update task
            task.assigned_miners = list(current_assigned) + new_miner_uids
            task.actual_miner_count = len(task.assigned_miners)
            task.updated_at = datetime.utcnow()
            
            # Update status if minimum met
            if len(task.assigned_miners) >= min_count:
                task.status = TaskStatusEnum.ASSIGNED
                if not task.distributed_at:
                    task.distributed_at = datetime.utcnow()
            
            session.commit()
            
            print(f"✅ Assigned {len(new_miner_uids)} miners to task {task_id} in PostgreSQL")
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"❌ Error assigning task to miners in PostgreSQL: {e}")
            return False
        finally:
            session.close()
    
    def get_available_miners(self, task_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get available miners"""
        session = self._get_session()
        try:
            query = session.query(MinerStatus).filter(
                MinerStatus.is_serving == True
            )
            
            # Filter by task type specialization if provided
            # PostgreSQL arrays: use ANY operator to check if task_type is in the array
            if task_type:
                # For PostgreSQL arrays, check if task_type is in the array using ANY
                # We'll use a simpler approach: check if the array contains the value
                # or if it's None/empty (which means all types are supported)
                query = query.filter(
                    or_(
                        MinerStatus.task_type_specialization == None,
                        MinerStatus.task_type_specialization == [],  # Empty array means all types
                        func.cast(task_type, String).in_(
                            func.unnest(MinerStatus.task_type_specialization)
                        )
                    )
                )
            
            # Filter by capacity
            query = query.filter(
                MinerStatus.assigned_task_count < MinerStatus.max_capacity
            )
            
            # Order by availability score
            miners = query.order_by(
                MinerStatus.availability_score.desc()
            ).limit(limit).all()
            
            return [self._miner_status_to_dict(miner) for miner in miners]
            
        except SQLAlchemyError as e:
            print(f"❌ Error getting available miners from PostgreSQL: {e}")
            return []
        finally:
            session.close()
    
    def update_miner_task_load(self, miner_uid: int, increment: bool = True):
        """Update miner task load"""
        session = self._get_session()
        try:
            miner_status = session.query(MinerStatus).filter(
                MinerStatus.uid == miner_uid
            ).first()
            
            if not miner_status:
                # Create new miner status
                miner_status = MinerStatus(
                    uid=miner_uid,
                    assigned_task_count=1 if increment else 0,
                    current_load=1 if increment else 0,
                    updated_at=datetime.utcnow()
                )
                session.add(miner_status)
            else:
                if increment:
                    miner_status.assigned_task_count += 1
                    miner_status.current_load = min(
                        miner_status.max_capacity,
                        miner_status.assigned_task_count
                    )
                else:
                    miner_status.assigned_task_count = max(0, miner_status.assigned_task_count - 1)
                    miner_status.current_load = min(
                        miner_status.max_capacity,
                        miner_status.assigned_task_count
                    )
                
                miner_status.updated_at = datetime.utcnow()
            
            session.commit()
            
        except SQLAlchemyError as e:
            session.rollback()
            print(f"❌ Error updating miner task load in PostgreSQL: {e}")
        finally:
            session.close()
    
    def get_miner_task_count(self, miner_uid: int) -> int:
        """Get miner task count"""
        session = self._get_session()
        try:
            # Count active tasks assigned to this miner using PostgreSQL array containment
            from sqlalchemy.dialects.postgresql import array
            count = session.query(Task).filter(
                and_(
                    Task.assigned_miners.op('@>')(array([miner_uid])),
                    Task.status.in_([
                        TaskStatusEnum.PENDING,
                        TaskStatusEnum.ASSIGNED,
                        TaskStatusEnum.IN_PROGRESS
                    ])
                )
            ).count()
            
            return count
            
        except SQLAlchemyError as e:
            print(f"❌ Error getting miner task count from PostgreSQL: {e}")
            return 0
        finally:
            session.close()
    
    def _task_to_dict(self, task: Task, session: Session = None) -> Dict[str, Any]:
        """Convert Task model to dictionary"""
        task_dict = {
            'task_id': task.task_id,
            'task_type': task.task_type.value if isinstance(task.task_type, Enum) else task.task_type,
            'status': task.status.value if isinstance(task.status, Enum) else task.status,
            'priority': task.priority.value if isinstance(task.priority, Enum) else task.priority,
            'source_language': task.source_language,
            'target_language': task.target_language,
            'model_id': task.model_id,
            'voice_name': task.voice_name,
            'speaker_wav_url': task.speaker_wav_url,
            'required_miner_count': task.required_miner_count,
            'min_miner_count': task.min_miner_count,
            'max_miner_count': task.max_miner_count,
            'actual_miner_count': task.actual_miner_count,
            'assigned_miners': task.assigned_miners or [],
            'user_id': task.user_id,
            'callback_url': task.callback_url,
            'user_metadata': task.user_metadata,
            'created_at': task.created_at,
            'updated_at': task.updated_at,
            'distributed_at': task.distributed_at,
            'completed_at': task.completed_at,
            'miner_responses': task.miner_responses or [],
            'best_response': task.best_response,
            'evaluation_data': task.evaluation_data,
            'validators_seen': getattr(task, 'validators_seen', []) or [],
            'validators_seen_timestamps': getattr(task, 'validators_seen_timestamps', {}) or {}
        }
        
        # Fetch input_text if input_text_id exists
        if task.input_text_id and session:
            from .postgresql_schema import TextContent
            text_content = session.query(TextContent).filter(
                TextContent.content_id == task.input_text_id
            ).first()
            if text_content:
                task_dict['input_text'] = {
                    'content_id': text_content.content_id,
                    'text': text_content.text,
                    'source_language': text_content.source_language,
                    'detected_language': text_content.detected_language,
                    'language_confidence': text_content.language_confidence,
                    'text_length': text_content.text_length,
                    'word_count': text_content.word_count,
                    'metadata': text_content.meta_data
                }
        
        # Fetch input_file if input_file_id exists
        if task.input_file_id and session:
            from .postgresql_schema import File
            file_obj = session.query(File).filter(
                File.file_id == task.input_file_id
            ).first()
            if file_obj:
                task_dict['input_file'] = {
                    'file_id': file_obj.file_id,
                    'file_name': file_obj.original_filename,
                    'file_type': file_obj.content_type,
                    'file_size': file_obj.file_size,
                    'storage_location': file_obj.storage_location,
                    'r2_key': file_obj.r2_key,
                    'public_url': file_obj.public_url
                }
        
        return task_dict
    
    def _miner_status_to_dict(self, miner: MinerStatus) -> Dict[str, Any]:
        """Convert MinerStatus model to dictionary"""
        return {
            'uid': miner.uid,
            'is_serving': miner.is_serving,
            'stake': miner.stake,
            'performance_score': miner.performance_score,
            'current_load': miner.current_load,
            'assigned_task_count': miner.assigned_task_count,
            'max_capacity': miner.max_capacity,
            'task_type_specialization': miner.task_type_specialization,
            'availability_score': miner.availability_score,
            'last_seen': miner.last_seen,
            'updated_at': miner.updated_at
        }

