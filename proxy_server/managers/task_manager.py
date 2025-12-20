"""
Task Manager for Enhanced Proxy Server
Handles task lifecycle, status updates, and miner assignments
"""

import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from database.enhanced_schema import TaskStatus, TaskPriority, DatabaseOperations
from database.postgresql_adapter import PostgreSQLAdapter

class TaskManager:
    def __init__(self, db):
        self.db = db
        # Check if using PostgreSQL adapter
        self.is_postgresql = isinstance(db, PostgreSQLAdapter)
        
        if not self.is_postgresql:
            # Legacy Firestore support
            from firebase_admin import firestore
            self.tasks_collection = db.collection('tasks')
            self.miner_responses_collection = db.collection('miner_responses')
            self.task_metrics_collection = db.collection('task_metrics')
        
        # Miner assignment configuration
        self.min_miners_per_task = 1
        self.max_miners_per_task = 10
        self.default_miners_per_task = 3
        
        # Import and initialize batch database manager
        try:
            # Batch manager removed - PostgreSQL doesn't need Firestore batch operations
            # from database.batch_manager import BatchDatabaseManager
            # self.batch_manager = BatchDatabaseManager(db)
            self.batch_manager = None  # Not used with PostgreSQL
            print("✅ Batch database manager initialized")
        except ImportError as e:
            print(f"⚠️ Could not import batch database manager: {e}")
            self.batch_manager = None
    
    async def create_task(self, task_data: Dict) -> str:
        """Create a new task"""
        try:
            # Prepare task data
            task_doc = {
                'task_type': task_data['task_type'],
                'input_file_id': task_data.get('input_file_id'),
                'source_language': task_data.get('source_language', 'en'),
                'target_language': task_data.get('target_language'),
                'priority': task_data.get('priority', 'normal'),
                'status': task_data.get('status', 'pending'),
                'assigned_miners': [],
                'required_miner_count': self._calculate_required_miner_count(task_data),
                'min_miner_count': task_data.get('min_miner_count', 1),
                'max_miner_count': task_data.get('max_miner_count', 5),
                'callback_url': task_data.get('callback_url'),
                'user_metadata': task_data.get('user_metadata', {}),
                'model_id': task_data.get('model_id'),
                'voice_name': task_data.get('voice_name'),
                'speaker_wav_url': task_data.get('speaker_wav_url')
            }
            
            # Use DatabaseOperations for PostgreSQL compatibility
            task_id = DatabaseOperations.create_task(self.db, task_doc)
            print(f"✅ Task created: {task_id} ({task_data['task_type']}) - Required miners: {task_doc['required_miner_count']}")
            
            return task_id
            
        except Exception as e:
            print(f"❌ Error creating task: {e}")
            raise

    def _calculate_required_miner_count(self, task_data: Dict) -> int:
        """Calculate the required number of miners for a task"""
        try:
            # Get requested miner count from task data
            requested_count = task_data.get('required_miner_count', self.default_miners_per_task)
            
            # Ensure minimum and maximum constraints
            if requested_count < self.min_miners_per_task:
                requested_count = self.min_miners_per_task
            elif requested_count > self.max_miners_per_task:
                requested_count = self.max_miners_per_task
            
            return requested_count
            
        except Exception as e:
            print(f"⚠️ Error calculating required miner count: {e}")
            return self.default_miners_per_task

    async def assign_miners_to_task(self, task_id: str, miner_uids: List[int]):
        """Assign miners to a specific task"""
        try:
            # Validate miner count constraints
            if len(miner_uids) < self.min_miners_per_task:
                raise ValueError(f"Task requires at least {self.min_miners_per_task} miners, got {len(miner_uids)}")
            
            if len(miner_uids) > self.max_miners_per_task:
                raise ValueError(f"Task cannot have more than {self.max_miners_per_task} miners, got {len(miner_uids)}")
            
            # Use DatabaseOperations for PostgreSQL compatibility
            min_count = self.min_miners_per_task
            max_count = self.max_miners_per_task
            success = DatabaseOperations.assign_task_to_miners(self.db, task_id, miner_uids, min_count, max_count)
            
            if success:
                print(f"✅ Task {task_id} assigned to {len(miner_uids)} miners (UIDs: {miner_uids})")
            else:
                raise Exception("Failed to assign miners to task")
            
        except Exception as e:
            print(f"❌ Failed to assign miners to task {task_id}: {e}")
            raise

    async def get_optimal_miner_count(self, task_type: str, priority: str = 'normal') -> int:
        """Get optimal number of miners for a task based on type and priority"""
        try:
            # Base miner count by task type
            base_counts = {
                'transcription': 2,  # Audio transcription benefits from multiple miners
                'tts': 2,            # TTS can have quality variations
                'summarization': 3,  # Summarization benefits from multiple perspectives
                'translation': 3     # Translation needs validation
            }
            
            base_count = base_counts.get(task_type, self.default_miners_per_task)
            
            # Adjust by priority
            priority_multipliers = {
                'low': 0.8,
                'normal': 1.0,
                'high': 1.3,
                'urgent': 1.5
            }
            
            multiplier = priority_multipliers.get(priority, 1.0)
            optimal_count = int(base_count * multiplier)
            
            # Ensure within constraints
            optimal_count = max(self.min_miners_per_task, min(optimal_count, self.max_miners_per_task))
            
            return optimal_count
            
        except Exception as e:
            print(f"⚠️ Error calculating optimal miner count: {e}")
            return self.default_miners_per_task

    async def update_task_status(self, task_id: str, status: str, **kwargs):
        """Update task status and additional fields"""
        try:
            # Convert status string to enum if needed
            status_enum = TaskStatus(status) if isinstance(status, str) else status
            success = DatabaseOperations.update_task_status(self.db, task_id, status_enum, **kwargs)
            
            if success:
                print(f"✅ Task {task_id} status updated to {status}")
            else:
                raise Exception("Failed to update task status")
            
        except Exception as e:
            print(f"❌ Failed to update task {task_id}: {e}")
            raise
    
    async def get_tasks_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """Get tasks by status"""
        try:
            status_enum = TaskStatus(status) if isinstance(status, str) else status
            tasks = DatabaseOperations.get_tasks_by_status(self.db, status_enum, limit)
            return tasks
            
        except Exception as e:
            print(f"❌ Failed to get tasks by status {status}: {e}")
            return []
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get a specific task by ID"""
        try:
            return DatabaseOperations.get_task(self.db, task_id)
        except Exception as e:
            print(f"❌ Error getting task {task_id}: {e}")
            return None
    
    async def delete_task(self, task_id: str) -> bool:
        """Delete a task and all associated data"""
        try:
            if self.is_postgresql:
                # PostgreSQL: Delete task (cascade will handle assignments)
                from database.postgresql_schema import Task
                session = self.db._get_session()
                try:
                    task = session.query(Task).filter(Task.task_id == task_id).first()
                    if task:
                        session.delete(task)
                        session.commit()
                        print(f"✅ Task {task_id} deleted successfully")
                        return True
                    else:
                        print(f"⚠️ Task {task_id} not found")
                        return False
                finally:
                    session.close()
            else:
                # Firestore (legacy)
                self.tasks_collection.document(task_id).delete()
                
                # Delete associated miner responses
                query = self.miner_responses_collection.where('task_id', '==', task_id)
                responses = query.stream()
                for doc in responses:
                    doc.reference.delete()
                
                print(f"✅ Task {task_id} deleted successfully")
                return True
            
        except Exception as e:
            print(f"❌ Failed to delete task {task_id}: {e}")
            return False
