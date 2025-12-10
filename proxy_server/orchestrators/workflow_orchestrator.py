"""
Workflow Orchestrator for Enhanced Proxy Server
Manages the complete task lifecycle, distribution, and monitoring
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from firebase_admin import firestore
from managers.task_manager import TaskManager
from managers.miner_response_handler import MinerResponseHandler
from database.enhanced_schema import TaskStatus, TaskPriority, COLLECTIONS, DatabaseOperations

class WorkflowOrchestrator:
    def __init__(self, db, task_manager=None, miner_status_manager=None):
        self.db = db
        self.task_manager = task_manager or TaskManager(db)
        self.miner_response_handler = MinerResponseHandler(db, self.task_manager)
        self.miner_status_manager = miner_status_manager
        self.running = False
        
    async def start_orchestration(self):
        """Start the main workflow orchestration"""
        if self.running:
            print("⚠️  Orchestration already running")
            return
        
        self.running = True
        print("🚀 Starting workflow orchestration...")
        
        # Start background tasks
        asyncio.create_task(self.task_distribution_loop())  # ENABLED - Task distribution needed
        asyncio.create_task(self.miner_monitoring_loop())
        asyncio.create_task(self.workflow_status_monitoring())
        asyncio.create_task(self.cleanup_old_tasks())
        asyncio.create_task(self.cleanup_stale_miners_loop())  # Clean up inactive miners
        
        print("✅ Workflow orchestration started successfully")
    
    async def stop_orchestration(self):
        """Stop the workflow orchestration"""
        self.running = False
        print("🛑 Workflow orchestration stopped")
    
    async def task_distribution_loop(self):
        """Main loop for distributing tasks to miners"""
        print("🔄 Starting task distribution loop...")
        
        while self.running:
            try:
                # Get pending tasks using enhanced operations
                pending_tasks = DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.PENDING, limit=10)
                
                for task in pending_tasks:
                    if not self.running:
                        break
                    
                    # Select optimal miners for this task
                    selected_miners = await self.select_optimal_miners(task)
                    
                    if selected_miners:
                        # Use enhanced database operations to assign miners
                        miner_uids = [m['uid'] for m in selected_miners]
                        success = DatabaseOperations.assign_task_to_miners(
                            self.db, 
                            task['task_id'], 
                            miner_uids
                        )
                        
                        if success:
                            print(f"✅ Task {task['task_id']} distributed to {len(selected_miners)} miners")
                        else:
                            print(f"❌ Failed to assign task {task['task_id']} to miners")
                    else:
                        print(f"⚠️  No available miners for task {task['task_id']}")
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                print(f"❌ Error in task distribution loop: {e}")
                await asyncio.sleep(10)
        
        print("🔄 Task distribution loop stopped")
    
    async def select_optimal_miners(self, task: Dict) -> List[Dict]:
        """Select optimal miners for a specific task using dynamic miner selection"""
        try:
            print(f"🔍 Selecting optimal miners for task {task['task_id']} ({task['task_type']})")
            
            # Get the task's required miner count
            required_count = task.get('required_miner_count', 3)
            task_type = task.get('task_type', 'transcription')
            
            # Use miner_status_manager if available for dynamic miner selection
            if self.miner_status_manager:
                try:
                    available_miners = await self.miner_status_manager.get_available_miners(
                        task_type=task_type,
                        min_count=1,
                        max_count=required_count
                    )
                    
                    if available_miners:
                        print(f"🎯 Selected {len(available_miners)} miners dynamically: {[m['uid'] for m in available_miners]}")
                        return available_miners
                    else:
                        print(f"⚠️  No available miners found via miner_status_manager for task type: {task_type}")
                except Exception as e:
                    print(f"⚠️  Error getting miners from miner_status_manager: {e}")
            
            # Fallback: Query miner status directly from database
            try:
                miner_status_collection = self.db.collection('miner_status')
                docs = miner_status_collection.stream()
                
                available_miners = []
                for doc in docs:
                    miner_data = doc.to_dict()
                    
                    # Check if miner is serving and available
                    if (miner_data.get('is_serving', False) and 
                        miner_data.get('current_load', 0) < miner_data.get('max_capacity', 5)):
                        
                        # Check task type specialization if specified
                        if task_type and miner_data.get('task_type_specialization'):
                            if task_type not in miner_data['task_type_specialization']:
                                continue
                        
                        available_miners.append({
                            'uid': miner_data.get('uid'),
                            'score': miner_data.get('performance_score', 0.5),
                            'current_load': miner_data.get('current_load', 0),
                            'availability_score': miner_data.get('availability_score', 0.5)
                        })
                
                # Sort by availability score (higher is better)
                available_miners.sort(key=lambda x: x.get('availability_score', 0), reverse=True)
                
                # Return up to required_count miners
                selected_miners = available_miners[:required_count]
                
                if selected_miners:
                    print(f"🎯 Selected {len(selected_miners)} miners from database: {[m['uid'] for m in selected_miners]}")
                    return selected_miners
                else:
                    print(f"⚠️  No available miners found in database for task type: {task_type}")
                    
            except Exception as e:
                print(f"⚠️  Error querying miner status from database: {e}")
            
            # Final fallback: Return empty list if no miners found
            print(f"❌ No available miners found for task {task['task_id']}")
            return []
            
        except Exception as e:
            print(f"❌ Error selecting optimal miners: {e}")
            return []
    
    async def send_task_to_miners(self, task: Dict, miners: List[Dict]):
        """Send task to selected miners via API"""
        for miner in miners:
            try:
                # Prepare task payload
                task_payload = {
                    'task_id': task['task_id'],
                    'task_type': task['task_type'],
                    'input_data': task['input_data'],
                    'language': task['language'],
                    'priority': task['priority'],
                    'deadline': datetime.now() + timedelta(seconds=task['estimated_completion_time'])
                }
                
                # Send to miner API (mock implementation)
                success = await self.send_to_miner_api(miner['uid'], task_payload)
                
                if success:
                    print(f"✅ Task {task['task_id']} sent to miner {miner['uid']}")
                else:
                    print(f"⚠️  Failed to send task {task['task_id']} to miner {miner['uid']}")
                    
            except Exception as e:
                print(f"❌ Error sending task to miner {miner['uid']}: {e}")
    
    async def send_to_miner_api(self, miner_uid: int, task_payload: Dict) -> bool:
        """Send task to miner API (mock implementation)"""
        try:
            # This is a mock implementation
            # In a real system, this would make HTTP requests to miner endpoints
            
            print(f"📤 Sending task to miner {miner_uid}: {task_payload['task_id']}")
            
            # Simulate API call delay
            await asyncio.sleep(0.1)
            
            # Mock success response
            return True
            
        except Exception as e:
            print(f"❌ Error in miner API call: {e}")
            return False
    
    async def miner_monitoring_loop(self):
        """Monitor miner performance and task completion"""
        print("👀 Starting miner monitoring loop...")
        
        while self.running:
            try:
                # Get assigned tasks
                distributed_tasks = DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.ASSIGNED, limit=50)
                
                for task in distributed_tasks:
                    if not self.running:
                        break
                    
                    # Check if all miners have completed
                    completion_status = await self.miner_response_handler.get_task_completion_status(task['task_id'])
                    
                    if completion_status.get('status') == TaskStatus.COMPLETED.value:
                        print(f"✅ Task {task['task_id']} completed by all miners")
                        
                        # Get best response for user
                        best_response = await self.miner_response_handler.get_best_response(task['task_id'])
                        if best_response:
                            print(f"🏆 Best response for task {task['task_id']}: Miner {best_response['miner_uid']}")
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                print(f"❌ Error in miner monitoring loop: {e}")
                await asyncio.sleep(15)
        
        print("👀 Miner monitoring loop stopped")
    
    async def workflow_status_monitoring(self):
        """Monitor overall workflow status and performance"""
        print("📊 Starting workflow status monitoring...")
        
        while self.running:
            try:
                # Get workflow statistics
                stats = await self.get_workflow_statistics()
                
                # Log statistics every minute
                print(f"📊 Workflow Status: {stats}")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"❌ Error in workflow status monitoring: {e}")
                await asyncio.sleep(60)
        
        print("📊 Workflow status monitoring stopped")
    
    async def get_workflow_statistics(self) -> Dict[str, Any]:
        """Get overall workflow statistics"""
        try:
            # Get task counts by status using enhanced operations
            pending_count = len(DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.PENDING))
            distributed_count = len(DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.ASSIGNED))
            in_progress_count = len(DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.IN_PROGRESS))
            completed_count = len(DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.COMPLETED))
            approved_count = len(DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.APPROVED))
            failed_count = len(DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.FAILED))
            
            # Also count tasks with "processing" status (legacy/invalid status that should be "in_progress")
            # Query directly to catch status mismatches
            processing_count = 0
            try:
                processing_tasks = self.db.collection('tasks').where('status', '==', 'processing').stream()
                processing_count = len(list(processing_tasks))
            except Exception as e:
                print(f"⚠️ Error counting 'processing' status tasks: {e}")
            
            # Total includes all statuses
            total_tasks = pending_count + distributed_count + in_progress_count + processing_count + completed_count + approved_count + failed_count
            
            return {
                'timestamp': datetime.now().isoformat(),
                'pending_tasks': pending_count,
                'distributed_tasks': distributed_count,
                'in_progress_tasks': in_progress_count + processing_count,  # Combine both
                'processing_tasks': processing_count,  # Legacy status count
                'completed_tasks': completed_count,
                'approved_tasks': approved_count,
                'failed_tasks': failed_count,
                'total_tasks': total_tasks
            }
            
        except Exception as e:
            print(f"❌ Error getting workflow statistics: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    async def cleanup_old_tasks(self):
        """Clean up old completed tasks to maintain database performance"""
        print("🧹 Starting cleanup loop...")
        
        while self.running:
            try:
                # Clean up tasks older than 7 days
                cutoff_date = datetime.now() - timedelta(days=7)
                
                # Get old completed tasks
                old_tasks = await self.get_old_completed_tasks(cutoff_date)
                
                for task in old_tasks:
                    if not self.running:
                        break
                    
                    # Archive old task
                    await self.archive_old_task(task)
                
                if old_tasks:
                    print(f"🧹 Cleaned up {len(old_tasks)} old tasks")
                
                await asyncio.sleep(3600)  # Run cleanup every hour
                
            except Exception as e:
                print(f"❌ Error in cleanup loop: {e}")
                await asyncio.sleep(3600)
        
        print("🧹 Cleanup loop stopped")
    
    async def cleanup_stale_miners_loop(self):
        """Periodically clean up stale/inactive miners from the database"""
        print("🧹 Starting stale miner cleanup loop...")
        
        while self.running:
            try:
                current_time = datetime.utcnow()
                miner_timeout = 900  # 15 minutes
                
                # Get all miners from database
                miner_status_collection = self.db.collection('miner_status')
                docs = miner_status_collection.stream()
                
                stale_miners = []
                for doc in docs:
                    miner_data = doc.to_dict()
                    last_seen = miner_data.get('last_seen')
                    miner_uid = miner_data.get('uid')
                    
                    if not last_seen:
                        # No last_seen timestamp - mark as stale
                        stale_miners.append((doc.id, miner_uid, 'No last_seen timestamp'))
                        continue
                    
                    # Handle different timestamp formats
                    try:
                        if isinstance(last_seen, datetime):
                            time_diff = (current_time - last_seen).total_seconds()
                        elif hasattr(last_seen, 'timestamp'):  # Firestore Timestamp
                            time_diff = (current_time.timestamp() - last_seen.timestamp())
                        elif isinstance(last_seen, str):
                            from dateutil import parser
                            last_seen_dt = parser.parse(last_seen)
                            time_diff = (current_time - last_seen_dt.replace(tzinfo=None)).total_seconds()
                        else:
                            # Unknown format - mark as stale
                            stale_miners.append((doc.id, miner_uid, f'Unknown timestamp format: {type(last_seen)}'))
                            continue
                        
                        # Check if miner is stale (not seen for more than timeout)
                        if time_diff > miner_timeout:
                            minutes_ago = time_diff / 60
                            stale_miners.append((doc.id, miner_uid, f'Last seen {minutes_ago:.1f} minutes ago'))
                    except Exception as e:
                        print(f"⚠️  Error checking last_seen for miner {miner_uid}: {e}")
                        stale_miners.append((doc.id, miner_uid, f'Error parsing timestamp: {e}'))
                
                # Remove stale miners from database
                removed_count = 0
                for miner_id, miner_uid, reason in stale_miners:
                    try:
                        miner_status_collection.document(miner_id).delete()
                        print(f"🗑️  Removed stale miner UID {miner_uid} ({reason})")
                        removed_count += 1
                    except Exception as e:
                        print(f"⚠️  Error removing stale miner {miner_uid}: {e}")
                
                if removed_count > 0:
                    print(f"🧹 Cleaned up {removed_count} stale miners")
                elif stale_miners:
                    print(f"⚠️  Found {len(stale_miners)} stale miners but failed to remove them")
                
                # Run cleanup every 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                print(f"❌ Error in stale miner cleanup loop: {e}")
                await asyncio.sleep(300)
        
        print("🧹 Stale miner cleanup loop stopped")
    
    async def get_old_completed_tasks(self, cutoff_date: datetime) -> List[Dict]:
        """Get old completed tasks for cleanup"""
        try:
            # This would query for old tasks in a real implementation
            # For now, return empty list
            return []
            
        except Exception as e:
            print(f"❌ Error getting old completed tasks: {e}")
            return []
    
    async def archive_old_task(self, task: Dict):
        """Archive an old completed task"""
        try:
            # Move to archive collection
            archive_collection = self.db.collection('archived_tasks')
            archive_collection.document(task['task_id']).set(task)
            
            # Delete from active tasks
            self.tasks_collection.document(task['task_id']).delete()
            
            print(f"🗄️  Archived old task: {task['task_id']}")
            
        except Exception as e:
            print(f"❌ Error archiving task: {e}")
    
    async def handle_miner_response(self, task_id: str, miner_uid: int, response_data: Dict):
        """Handle response from a miner"""
        try:
            await self.miner_response_handler.handle_miner_response(task_id, miner_uid, response_data)
        except Exception as e:
            print(f"❌ Error handling miner response in orchestrator: {e}")
            raise
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get comprehensive task status"""
        try:
            # Get basic task info
            task = self.task_manager.get_task(task_id)  # Remove await since method is now sync
            if not task:
                return {'error': 'Task not found'}
            
            # Get completion status
            completion_status = await self.miner_response_handler.get_task_completion_status(task_id)
            
            # Get best response if available
            best_response = None
            if task['status'] in [TaskStatus.COMPLETED.value, TaskStatus.APPROVED.value]:
                best_response = await self.miner_response_handler.get_best_response(task_id)
            
            return {
                'task': task,
                'completion_status': completion_status,
                'best_response': best_response
            }
            
        except Exception as e:
            print(f"❌ Error getting task status: {e}")
            return {'error': str(e)}
