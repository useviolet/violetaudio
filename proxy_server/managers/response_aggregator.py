"""
Response Aggregator for Enhanced Proxy Server
Buffers miner responses and flushes them in batches to reduce Firestore quota usage
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict
from database.postgresql_adapter import PostgreSQLAdapter
from database.enhanced_schema import DatabaseOperations, TaskStatus
import time
import json

class ResponseAggregator:
    def __init__(self, db):
        self.db = db
        # PostgreSQL only - no Firestore support
        self.is_postgresql = isinstance(db, PostgreSQLAdapter)
        self.response_buffer = defaultdict(list)
        self.buffer_timeout = 60  # 60 seconds
        self.min_responses_to_flush = 3  # Flush after 3 miners respond
        self.last_flush_check = time.time()
        self.flush_check_interval = 30  # Check for timeouts every 30 seconds
        
        # Start background flush checker
        asyncio.create_task(self._background_flush_checker())
    
    async def buffer_miner_response(self, task_id: str, miner_uid: int, response: Dict):
        """Buffer miner response instead of immediate database update"""
        try:
            # Add response to buffer
            self.response_buffer[task_id].append({
                'miner_uid': miner_uid,
                'response': response,
                'timestamp': datetime.now()
            })
            
            print(f"📥 Buffered response from miner {miner_uid} for task {task_id}")
            print(f"   Buffer size: {len(self.response_buffer[task_id])}")
            
            # Check if we should flush this task's responses
            await self._check_flush_task(task_id)
            
        except Exception as e:
            print(f"❌ Error buffering response: {e}")
    
    async def _check_flush_task(self, task_id: str):
        """Check if task responses should be flushed to database"""
        responses = self.response_buffer[task_id]
        
        if not responses:
            return
        
        # Flush if:
        # 1. We have enough responses (3+ miners)
        # 2. Timeout reached
        # 3. Task is completed
        
        should_flush = (
            len(responses) >= self.min_responses_to_flush or
            (datetime.now() - responses[0]['timestamp']).seconds >= self.buffer_timeout
        )
        
        if should_flush:
            await self._flush_task_responses(task_id)
    
    async def _flush_task_responses(self, task_id: str):
        """Flush all buffered responses for a task in ONE database operation"""
        responses = self.response_buffer[task_id]
        
        if not responses:
            return
        
        try:
            print(f"🔄 Flushing {len(responses)} responses for task {task_id}")
            
            # Prepare response data for database
            # Serialize datetime objects to ISO format strings for JSON storage
            response_data = []
            for r in responses:
                # Convert datetime to ISO format string
                submitted_at = r['timestamp']
                if isinstance(submitted_at, datetime):
                    submitted_at = submitted_at.isoformat()
                
                response_info = {
                    'miner_uid': r['miner_uid'],
                    'response': r['response'],
                    'submitted_at': submitted_at
                }
                response_data.append(response_info)
            
            # Update task with all responses (PostgreSQL only)
            # Get current task
            task = DatabaseOperations.get_task(self.db, task_id)
            if not task:
                print(f"❌ Task {task_id} not found")
                return
            
            # Merge new responses with existing ones
            existing_responses = task.get('miner_responses', [])
            if not isinstance(existing_responses, list):
                existing_responses = []
            
            # Serialize any datetime objects in existing responses
            existing_responses = self._serialize_datetime_in_responses(existing_responses)
            
            # Add new responses
            all_responses = existing_responses + response_data
            
            # Final serialization pass to ensure all datetime objects are strings
            all_responses = self._serialize_datetime_in_responses(all_responses)
            
            # Determine status: Set to COMPLETED based on min_miner_count or timeout
            # Get task to check assigned_miners count and min_miner_count
            task = DatabaseOperations.get_task(self.db, task_id)
            if not task:
                print(f"❌ Task {task_id} not found during flush")
                return
            
            assigned_count = len(task.get('assigned_miners', [])) if task else 0
            response_count = len(all_responses)
            min_miner_count = task.get('min_miner_count', 1)
            
            # Get task age for timeout check
            task_created_at = task.get('created_at')
            if isinstance(task_created_at, str):
                from dateutil import parser
                task_created_at = parser.parse(task_created_at)
            task_age_seconds = (datetime.now() - task_created_at).total_seconds() if task_created_at else 0
            task_age_hours = task_age_seconds / 3600
            
            # Task completion criteria (same as MinerResponseHandler):
            # 1. Minimum miners responded OR
            # 2. Task is old enough (1 hour) and has at least 1 response OR
            # 3. All assigned miners responded
            if response_count >= min_miner_count:
                new_status = TaskStatus.COMPLETED
                completion_reason = f"min_miner_count met ({response_count} >= {min_miner_count})"
            elif task_age_hours >= 1.0 and response_count >= 1:
                new_status = TaskStatus.COMPLETED
                completion_reason = f"timeout reached ({task_age_hours:.1f}h) with {response_count} response(s)"
            elif assigned_count > 0 and response_count >= assigned_count:
                new_status = TaskStatus.COMPLETED
                completion_reason = f"all assigned miners responded ({response_count}/{assigned_count})"
            else:
                # Still waiting for more responses
                new_status = TaskStatus.ASSIGNED
                completion_reason = None
            
            # Add completion metadata if completing
            update_kwargs = {
                'response_count': len(all_responses),
                'actual_response_count': response_count,
                'expected_response_count': assigned_count
            }
            if completion_reason:
                update_kwargs['completion_reason'] = completion_reason
                update_kwargs['completed_at'] = datetime.now()
            
            # Update task
            DatabaseOperations.update_task_status(
                self.db, task_id, new_status,
                miner_responses=all_responses,
                **update_kwargs
            )
            
            # Clear buffer for this task
            del self.response_buffer[task_id]
            
            print(f"✅ Successfully flushed {len(responses)} responses for task {task_id}")
            
        except Exception as e:
            print(f"❌ Response flush failed for task {task_id}: {e}")
            # Keep responses in buffer for retry
            print(f"   Responses kept in buffer for retry")
    
    async def _background_flush_checker(self):
        """Background task to check for timeouts and flush old responses"""
        while True:
            try:
                current_time = time.time()
                
                # Check if it's time to look for timeouts
                if current_time - self.last_flush_check >= self.flush_check_interval:
                    await self._check_timeouts()
                    self.last_flush_check = current_time
                
                # Sleep for a short interval
                await asyncio.sleep(10)
                
            except Exception as e:
                print(f"❌ Background flush checker error: {e}")
                await asyncio.sleep(30)  # Longer sleep on error
    
    async def _check_timeouts(self):
        """Check for tasks with timed-out responses and flush them"""
        try:
            current_time = datetime.now()
            tasks_to_flush = []
            
            for task_id, responses in self.response_buffer.items():
                if not responses:
                    continue
                
                # Check if oldest response has timed out
                oldest_response = min(responses, key=lambda x: x['timestamp'])
                time_since_oldest = (current_time - oldest_response['timestamp']).seconds
                
                if time_since_oldest >= self.buffer_timeout:
                    tasks_to_flush.append(task_id)
            
            # Flush timed-out tasks
            for task_id in tasks_to_flush:
                print(f"⏰ Flushing timed-out responses for task {task_id}")
                await self._flush_task_responses(task_id)
                
        except Exception as e:
            print(f"❌ Timeout check failed: {e}")
    
    async def force_flush_all(self):
        """Force flush all buffered responses (useful for shutdown)"""
        try:
            print(f"🔄 Force flushing all buffered responses...")
            
            task_ids = list(self.response_buffer.keys())
            for task_id in task_ids:
                await self._flush_task_responses(task_id)
            
            print(f"✅ All responses flushed")
            
        except Exception as e:
            print(f"❌ Force flush failed: {e}")
    
    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get statistics about current buffer state"""
        try:
            total_responses = sum(len(responses) for responses in self.response_buffer.values())
            total_tasks = len(self.response_buffer)
            
            return {
                'buffered_tasks': total_tasks,
                'buffered_responses': total_responses,
                'buffer_timeout': self.buffer_timeout,
                'min_responses_to_flush': self.min_responses_to_flush,
                'tasks_in_buffer': list(self.response_buffer.keys())
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def clear_buffer(self):
        """Clear all buffered responses (use with caution)"""
        try:
            self.response_buffer.clear()
            print("🧹 Response buffer cleared")
        except Exception as e:
            print(f"❌ Buffer clear failed: {e}")
    
    def _serialize_datetime_in_responses(self, responses: List[Dict]) -> List[Dict]:
        """Recursively serialize datetime objects in response data to ISO format strings"""
        if not isinstance(responses, list):
            return responses
        
        serialized = []
        for response in responses:
            if not isinstance(response, dict):
                serialized.append(response)
                continue
            
            serialized_response = {}
            for key, value in response.items():
                if isinstance(value, datetime):
                    serialized_response[key] = value.isoformat()
                elif isinstance(value, dict):
                    # Recursively serialize nested dicts
                    serialized_response[key] = self._serialize_datetime_in_dict(value)
                elif isinstance(value, list):
                    # Recursively serialize lists
                    serialized_response[key] = self._serialize_datetime_in_list(value)
                else:
                    serialized_response[key] = value
            serialized.append(serialized_response)
        
        return serialized
    
    def _serialize_datetime_in_dict(self, data: Dict) -> Dict:
        """Recursively serialize datetime objects in a dictionary"""
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = self._serialize_datetime_in_dict(value)
            elif isinstance(value, list):
                result[key] = self._serialize_datetime_in_list(value)
            else:
                result[key] = value
        return result
    
    def _serialize_datetime_in_list(self, data: List) -> List:
        """Recursively serialize datetime objects in a list"""
        if not isinstance(data, list):
            return data
        
        result = []
        for item in data:
            if isinstance(item, datetime):
                result.append(item.isoformat())
            elif isinstance(item, dict):
                result.append(self._serialize_datetime_in_dict(item))
            elif isinstance(item, list):
                result.append(self._serialize_datetime_in_list(item))
            else:
                result.append(item)
        return result
