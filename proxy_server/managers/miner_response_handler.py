"""
Miner Response Handler for Enhanced Proxy Server
Manages miner responses, task completion tracking, and immediate user feedback
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from database.enhanced_schema import TaskStatus, COLLECTIONS, DatabaseOperations
from database.postgresql_adapter import PostgreSQLAdapter

class MinerResponseHandler:
    def __init__(self, db, task_manager=None):
        self.db = db
        self.task_manager = task_manager
        self.is_postgresql = isinstance(db, PostgreSQLAdapter)
        
        if not self.is_postgresql:
            # Legacy Firestore support
            from firebase_admin import firestore
            self.tasks_collection = db.collection('tasks')
        
        # Import and initialize response aggregator
        try:
            from .response_aggregator import ResponseAggregator
            self.response_aggregator = ResponseAggregator(db)
            print("✅ Response aggregator initialized")
        except ImportError as e:
            print(f"⚠️ Could not import response aggregator: {e}")
            self.response_aggregator = None
    
    async def handle_miner_response(self, task_id: str, miner_uid: int, response_data: Dict) -> bool:
        """Handle miner response for a specific task"""
        try:
            print(f"📥 Handling miner {miner_uid} response for task {task_id}")
            
            # 🔒 DUPLICATE PROTECTION: Check if miner already responded to this task
            current_task = DatabaseOperations.get_task(self.db, task_id)
            if not current_task:
                print(f"❌ Task {task_id} not found in database")
                return False
            
            task_data = current_task
            miner_responses = task_data.get('miner_responses', [])
            
            # Check for duplicate responses from the same miner
            for existing_response in miner_responses:
                if existing_response.get('miner_uid') == miner_uid:
                    print(f"⚠️ Miner {miner_uid} already responded to task {task_id}, ignoring duplicate response")
                    print(f"   Previous response timestamp: {existing_response.get('submitted_at', 'unknown')}")
                    print(f"   Duplicate response timestamp: {response_data.get('submitted_at', 'unknown')}")
                    return False
            
            print(f"✅ No duplicate response detected for miner {miner_uid} on task {task_id}")
            
            # Create response document
            response_doc = {
                'miner_uid': miner_uid,
                'task_id': task_id,
                'response_data': response_data,
                'submitted_at': datetime.utcnow(),
                'status': 'completed'
            }
            
            # Add accuracy and speed scores if available
            if 'accuracy_score' in response_data:
                response_doc['accuracy_score'] = response_data['accuracy_score']
            if 'speed_score' in response_data:
                response_doc['speed_score'] = response_data['speed_score']
            if 'processing_time' in response_data:
                response_doc['processing_time'] = response_data['processing_time']
            
            # Handle file uploads for specific task types
            task_type = task_data.get('task_type')
            if task_type == 'tts' and 'audio_file' in response_data:
                try:
                    # Store TTS audio file
                    audio_data = response_data['audio_file']
                    file_id = self.file_manager.store_file(
                        audio_data, 
                        f"tts_audio_{task_id}_{miner_uid}.wav",
                        'audio/wav',
                        'user_audio'
                    )
                    response_doc['audio_file_id'] = file_id
                    print(f"✅ TTS audio file stored: {file_id}")
                    
                except Exception as e:
                    print(f"⚠️  Failed to store TTS audio file: {e}")
            
            # Store response directly in task document (embedded approach)
            # Get current task data again (in case it changed)
            current_task_data = DatabaseOperations.get_task(self.db, task_id)
            if not current_task_data:
                print(f"❌ Task {task_id} not found in database during response storage")
                return False
            
            current_miner_responses = current_task_data.get('miner_responses', [])
            
            # 🔒 DUPLICATE PROTECTION: Double-check for duplicates before storing
            for existing_response in current_miner_responses:
                if existing_response.get('miner_uid') == miner_uid:
                    print(f"⚠️ Miner {miner_uid} already responded to task {task_id} (race condition detected), ignoring duplicate")
                    return False
            
            # Add new response to the list
            if isinstance(current_miner_responses, list):
                current_miner_responses.append(response_doc)
            else:
                # Fallback for old dictionary format
                current_miner_responses = [response_doc]
            
            # Update task with embedded response
            update_data = {
                'miner_responses': current_miner_responses,
                'updated_at': datetime.utcnow()
            }
            
            # Check if task should be marked as completed
            # Use min_miner_count instead of all assigned miners to prevent tasks from getting stuck
            assigned_miners = current_task_data.get('assigned_miners', [])
            assigned_count = len(assigned_miners) if assigned_miners else 0
            response_count = len(current_miner_responses)
            min_miner_count = current_task_data.get('min_miner_count', 1)
            required_miner_count = current_task_data.get('required_miner_count', 3)
            
            # Get task age to check for timeout
            task_created_at = current_task_data.get('created_at')
            if isinstance(task_created_at, str):
                from dateutil import parser
                task_created_at = parser.parse(task_created_at)
            task_age_seconds = (datetime.utcnow() - task_created_at).total_seconds() if task_created_at else 0
            task_age_hours = task_age_seconds / 3600
            
            # Task completion criteria:
            # 1. Minimum miners responded (min_miner_count) OR
            # 2. Task is old enough (1 hour) and has at least 1 response OR
            # 3. All assigned miners responded (original behavior)
            should_complete = False
            completion_reason = ""
            
            if response_count >= min_miner_count:
                should_complete = True
                completion_reason = f"min_miner_count met ({response_count} >= {min_miner_count})"
            elif task_age_hours >= 1.0 and response_count >= 1:
                should_complete = True
                completion_reason = f"timeout reached ({task_age_hours:.1f}h) with {response_count} response(s)"
            elif assigned_count > 0 and response_count >= assigned_count:
                should_complete = True
                completion_reason = f"all assigned miners responded ({response_count}/{assigned_count})"
            
            if should_complete:
                update_data['status'] = TaskStatus.COMPLETED.value
                update_data['all_miners_completed_at'] = datetime.utcnow()
                update_data['completed_at'] = datetime.utcnow()
                update_data['completion_reason'] = completion_reason
                update_data['actual_response_count'] = response_count
                update_data['expected_response_count'] = assigned_count
                
                print(f"✅ Task {task_id} COMPLETED: {response_count}/{assigned_count} miners responded ({completion_reason})")
                
                # Calculate best response from available responses
                best_response = self._calculate_best_response(current_miner_responses)
                if best_response:
                    update_data['best_response'] = best_response
                
                # Decrement miner load only for miners who actually responded
                responded_miner_uids = [r.get('miner_uid') for r in current_miner_responses if r.get('miner_uid')]
                for miner_uid in responded_miner_uids:
                    DatabaseOperations.update_miner_task_load(self.db, miner_uid, increment=False)
                    print(f"📉 Decremented miner {miner_uid} load (task {task_id} completed)")
                
                # Note: Miners who didn't respond will have their load decremented by timeout cleanup
            
            # Use response aggregator if available, otherwise fall back to immediate update
            if self.response_aggregator:
                # Buffer response for batch processing
                await self.response_aggregator.buffer_miner_response(task_id, miner_uid, response_doc)
                print(f"✅ Miner {miner_uid} response buffered for task {task_id}")
            else:
                # Fallback to immediate update using DatabaseOperations
                DatabaseOperations.add_miner_response(self.db, task_id, miner_uid, response_doc)
                # Also update status if needed
                if 'status' in update_data:
                    DatabaseOperations.update_task_status(self.db, task_id, TaskStatus(update_data['status']), **{k: v for k, v in update_data.items() if k != 'status'})
                print(f"✅ Miner {miner_uid} response stored immediately in task {task_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error handling miner response: {e}")
            return False
    
    def get_duplicate_protection_stats(self) -> Dict[str, Any]:
        """Get statistics about duplicate response protection"""
        try:
            # Count tasks with multiple responses from same miner
            duplicate_count = 0
            total_responses = 0
            
            # Query all tasks to analyze response patterns
            if self.is_postgresql:
                # PostgreSQL: Get all tasks
                from database.postgresql_schema import Task
                session = self.db._get_session()
                try:
                    tasks = session.query(Task).all()
                    for task in tasks:
                        task_data = self.db._task_to_dict(task)
                        miner_responses = task_data.get('miner_responses', [])
                        
                        if isinstance(miner_responses, list):
                            total_responses += len(miner_responses)
                            
                            # Check for duplicate miner UIDs
                            miner_uids = [resp.get('miner_uid') for resp in miner_responses]
                            if len(miner_uids) != len(set(miner_uids)):
                                duplicate_count += 1
                finally:
                    session.close()
            else:
                # Firestore (legacy)
                tasks = self.tasks_collection.stream()
                for task_doc in tasks:
                    task_data = task_doc.to_dict()
                    miner_responses = task_data.get('miner_responses', [])
                    
                    if isinstance(miner_responses, list):
                        total_responses += len(miner_responses)
                        
                        # Check for duplicate miner UIDs
                        miner_uids = [resp.get('miner_uid') for resp in miner_responses]
                        if len(miner_uids) != len(set(miner_uids)):
                            duplicate_count += 1
            
            return {
                'duplicate_protection_active': True,
                'total_responses_processed': total_responses,
                'tasks_with_duplicate_responses': duplicate_count,
                'duplicate_protection_effectiveness': f"{((total_responses - duplicate_count) / total_responses * 100):.2f}%" if total_responses > 0 else "100%"
            }
        except Exception as e:
            print(f"⚠️ Error getting duplicate protection stats: {e}")
            return {'error': str(e)}
    
    def _calculate_best_response(self, miner_responses: List[Dict]) -> Optional[Dict]:
        """Calculate the best response based on accuracy and speed scores"""
        try:
            if not miner_responses:
                return None
            
            # Score each response
            scored_responses = []
            for response in miner_responses:
                accuracy = response.get('accuracy_score', 0.0)
                speed = response.get('speed_score', 0.0)
                processing_time = response.get('processing_time', 0.0)
                
                # Combined score (accuracy weighted more than speed)
                combined_score = (accuracy * 0.7) + (speed * 0.3)
                
                scored_responses.append({
                    'response': response,
                    'score': combined_score,
                    'processing_time': processing_time
                })
            
            # Sort by score (highest first), then by processing time (lowest first)
            scored_responses.sort(key=lambda x: (x['score'], -x['processing_time']), reverse=True)
            
            # Return the best response
            return scored_responses[0]['response']
            
        except Exception as e:
            print(f"⚠️ Error calculating best response: {e}")
            return None
    
    async def get_task_completion_status(self, task_id: str) -> Dict[str, Any]:
        """Get task completion status and miner response summary"""
        try:
            task_data = DatabaseOperations.get_task(self.db, task_id)
            if not task_data:
                return {'error': 'Task not found'}
            miner_responses = task_data.get('miner_responses', [])
            
            response_statuses = {}
            completed_count = 0
            
            # Handle miner_responses as a list (enhanced schema)
            if isinstance(miner_responses, list):
                for response in miner_responses:
                    miner_uid = response.get('miner_uid')
                    status = response.get('status', 'pending')
                    
                    if miner_uid:
                        response_statuses[miner_uid] = {
                            'status': status,
                            'processing_time': response.get('processing_time'),
                            'accuracy_score': response.get('accuracy_score'),
                            'speed_score': response.get('speed_score')
                        }
                        
                        if status == 'completed':
                            completed_count += 1
            else:
                # Fallback for old dictionary format
                for miner_uid, response in miner_responses.items():
                    status = response.get('status', 'pending')
                    
                    response_statuses[miner_uid] = {
                        'status': status,
                        'processing_time': response.get('processing_time'),
                        'accuracy_score': response.get('accuracy_score'),
                        'speed_score': response.get('speed_score')
                    }
                    
                    if status == 'completed':
                        completed_count += 1
            
            return {
                'task_id': task_id,
                'status': task_data['status'],
                'required_miners': task_data.get('required_miner_count', 3),
                'assigned_miners': len(task_data.get('assigned_miners', [])),
                'completed_miners': completed_count,
                'miner_statuses': response_statuses,
                'first_response': task_data.get('first_response'),
                'all_completed_at': task_data.get('all_miners_completed_at'),
                'best_response': task_data.get('best_response')
            }
            
        except Exception as e:
            print(f"❌ Error getting task completion status: {e}")
            return {'error': str(e)}
    
    async def get_best_response(self, task_id: str) -> Optional[Dict]:
        """Get the best response for a completed task"""
        try:
            task_data = DatabaseOperations.get_task(self.db, task_id)
            if not task_data:
                return None
            
            return task_data.get('best_response')
            
        except Exception as e:
            print(f"❌ Error getting best response: {e}")
            return None
    
    async def check_all_miners_completed(self, task_id: str) -> bool:
        """Check if all assigned miners have completed the task"""
        try:
            completion_status = await self.get_task_completion_status(task_id)
            
            if 'error' in completion_status:
                return False
            
            assigned_count = completion_status.get('assigned_miners', 0)
            completed_count = completion_status.get('completed_miners', 0)
            
            return assigned_count > 0 and assigned_count == completed_count
            
        except Exception as e:
            print(f"❌ Error checking miner completion: {e}")
            return False
    
    async def _update_task_status(self, task_id: str, status: str, **kwargs):
        """Update task status with additional fields"""
        try:
            status_enum = TaskStatus(status) if isinstance(status, str) else status
            DatabaseOperations.update_task_status(self.db, task_id, status_enum, **kwargs)
            
        except Exception as e:
            print(f"❌ Error updating task status: {e}")
    
    async def notify_validators_task_ready(self, task_id: str):
        """Notify validators that a task is ready for evaluation"""
        try:
            # Update task status to indicate it's ready for validator evaluation
            await self._update_task_status(task_id, 'ready_for_evaluation')
            
            print(f"📢 Task {task_id} marked as ready for validator evaluation")
            
        except Exception as e:
            print(f"❌ Error notifying validators: {e}")
    
    async def cleanup_failed_responses(self, task_id: str):
        """Clean up failed or invalid miner responses"""
        try:
            task_data = DatabaseOperations.get_task(self.db, task_id)
            if not task_data:
                return
            
            miner_responses = task_data.get('miner_responses', [])
            
            # Filter out failed responses
            valid_responses = []
            for response in miner_responses:
                if response.get('status') != 'failed':
                    valid_responses.append(response)
            
            # Update task with cleaned responses
            if len(valid_responses) != len(miner_responses):
                DatabaseOperations.update_task_status(self.db, task_id, TaskStatus(task_data.get('status', 'pending')), 
                                                     miner_responses=valid_responses)
                print(f"🧹 Cleaned up failed responses for task {task_id}")
            
        except Exception as e:
            print(f"❌ Error cleaning up failed responses: {e}")
