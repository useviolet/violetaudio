"""
Workflow Orchestrator for Enhanced Proxy Server
Manages the complete task lifecycle, distribution, and monitoring
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from managers.task_manager import TaskManager
from managers.miner_response_handler import MinerResponseHandler
from database.enhanced_schema import TaskStatus, TaskPriority, COLLECTIONS, DatabaseOperations
from database.postgresql_adapter import PostgreSQLAdapter

class WorkflowOrchestrator:
    def __init__(self, db, task_manager=None, miner_status_manager=None):
        self.db = db
        # PostgreSQL only - no Firestore support
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
        asyncio.create_task(self.cleanup_old_tasks())  # Stale tasks with partial responses (every 15 min)
        asyncio.create_task(self.cleanup_very_old_tasks())  # Very old tasks cleanup (once per day)
        asyncio.create_task(self.cleanup_stale_miners_loop())  # Clean up inactive miners
        
        print("✅ Workflow orchestration started successfully")
    
    async def stop_orchestration(self):
        """Stop the workflow orchestration"""
        self.running = False
        print("🛑 Workflow orchestration stopped")
    
    async def task_distribution_loop(self):
        """Main loop for distributing tasks to miners with min/max constraints"""
        print("🔄 Starting task distribution loop...")
        
        while self.running:
            try:
                # Get pending and assigned tasks (assigned tasks might need more miners)
                pending_tasks = DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.PENDING, limit=10)
                assigned_tasks = DatabaseOperations.get_tasks_by_status(self.db, TaskStatus.ASSIGNED, limit=10)
                
                all_tasks = pending_tasks + assigned_tasks
                
                # Process tasks in parallel
                if all_tasks:
                    # Create tasks for parallel processing
                    task_coroutines = [self._process_single_task(task) for task in all_tasks]
                    # Execute all tasks in parallel
                    await asyncio.gather(*task_coroutines, return_exceptions=True)
                
                await asyncio.sleep(180)  # Check every 3 minutes
                
            except Exception as e:
                print(f"❌ Error in task distribution loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(180)
        
        print("🔄 Task distribution loop stopped")
    
    async def _process_single_task(self, task: Dict[str, Any]) -> None:
        """Process a single task for distribution (runs in parallel)"""
        try:
            if not self.running:
                return
            
            task_id = task['task_id']
            task_type = task.get('task_type', 'transcription')
            
            # Get min/max miner counts from task
            min_count = task.get('min_miner_count', 1)
            max_count = task.get('max_miner_count', task.get('required_miner_count', 3))
            required_count = task.get('required_miner_count', 3)
            
            # Use required_count as default max if max_miner_count not set
            if 'max_miner_count' not in task:
                max_count = required_count
            
            # Get currently assigned miners
            current_assigned = task.get('assigned_miners', [])
            current_count = len(current_assigned)
            
            # Check if we need more miners
            if current_count >= max_count:
                return  # Already at maximum, skip
            
            # Calculate how many more miners we need
            needed_count = max_count - current_count
            
            # Ensure we meet minimum if below it
            if current_count < min_count:
                needed_count = max(needed_count, min_count - current_count)
            
            # Only process if we actually need miners
            if needed_count > 0:
                # Get available miners, excluding those already assigned
                available_miners = await self.select_optimal_miners(task, exclude_miners=current_assigned, limit=needed_count * 2)
                
                if available_miners:
                    # Filter out already assigned miners (double-check)
                    new_miners = [m for m in available_miners if m['uid'] not in current_assigned]
                    
                    # Take only what we need
                    selected_miners = new_miners[:needed_count]
                    miner_uids = [m['uid'] for m in selected_miners]
                    
                    if miner_uids:
                        # Use enhanced database operations to assign miners with min/max
                        success = DatabaseOperations.assign_task_to_miners(
                            self.db, 
                            task_id, 
                            miner_uids,
                            min_count=min_count,
                            max_count=max_count
                        )
                        
                        if success:
                            print(f"✅ Task {task_id} assigned {len(selected_miners)} miner(s)")
                        # Don't log failures - they're expected when no miners available
        except Exception as e:
            # Log errors but don't stop other parallel tasks
            print(f"⚠️ Error processing task {task.get('task_id', 'unknown')}: {e}")
    
    async def select_optimal_miners(self, task: Dict, exclude_miners: List[int] = None, limit: int = None) -> List[Dict]:
        """Select optimal miners for a specific task using dynamic miner selection"""
        try:
            task_id = task.get('task_id', 'unknown')
            task_type = task.get('task_type', 'transcription')
            required_count = task.get('required_miner_count', 3)
            
            # Use limit if provided, otherwise use required_count
            if limit is None:
                limit = required_count
            
            exclude_miners = exclude_miners or []
            
            # Reduce logging - only log when actually selecting miners
            # print(f"🔍 Selecting optimal miners for task {task_id} ({task_type})")
            
            # Use miner_status_manager if available for dynamic miner selection
            if self.miner_status_manager:
                try:
                    available_miners = await self.miner_status_manager.get_available_miners(
                        task_type=task_type,
                        min_count=1,
                        max_count=limit * 2  # Get more than needed to filter out excluded
                    )
                    
                    # Filter out excluded miners (already assigned)
                    if exclude_miners:
                        available_miners = [m for m in available_miners if m.get('uid') not in exclude_miners]
                    
                    # Limit to requested count
                    if available_miners:
                        selected = available_miners[:limit]
                        print(f"🎯 Selected {len(selected)} miners dynamically: {[m['uid'] for m in selected]}")
                        return selected
                    else:
                        # Silently handle no miners - it's expected
                        pass
                except Exception as e:
                    # Reduce logging - only log unexpected errors
                    if "collection" not in str(e):
                        pass  # Silently handle expected errors
            
            # Fallback: Query miner status directly from database
            try:
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
                
                available_miners = []
                
                # Process miners (PostgreSQL dicts)
                for doc in docs:
                    miner_data = doc  # Already a dict
                    
                    miner_uid = miner_data.get('uid')
                    
                    # Skip excluded miners (already assigned)
                    if miner_uid in exclude_miners:
                        continue
                    
                    # Check if miner is serving and available
                    # Use both current_load and assigned_task_count for capacity check
                    current_load = miner_data.get('current_load', 0)
                    assigned_task_count = miner_data.get('assigned_task_count', 0)
                    max_capacity = miner_data.get('max_capacity', 5)
                    effective_load = max(current_load, assigned_task_count)
                    
                    if (miner_data.get('is_serving', False) and 
                        effective_load < max_capacity):
                        
                        # Check task type specialization if specified
                        if task_type and miner_data.get('task_type_specialization'):
                            if task_type not in miner_data['task_type_specialization']:
                                continue
                        
                        available_miners.append({
                            'uid': miner_uid,
                            'score': miner_data.get('performance_score', 0.5),
                            'current_load': effective_load,
                            'assigned_task_count': assigned_task_count,
                            'availability_score': miner_data.get('availability_score', 0.5)
                        })
                
                # Sort by availability score (higher is better)
                available_miners.sort(key=lambda x: x.get('availability_score', 0), reverse=True)
                
                # Return up to limit miners
                selected_miners = available_miners[:limit]
                
                if selected_miners:
                    # Reduce logging - only log when miners are actually selected
                    return selected_miners
                else:
                    # Only log if it's a real issue (not just no miners available)
                    pass
                    
            except Exception as e:
                # Reduce logging noise - only log unexpected errors
                if "collection" not in str(e) and "docs" not in str(e):
                    print(f"⚠️  Error querying miner status: {e}")
            
            # Final fallback: Return empty list if no miners found (no logging - expected behavior)
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
                
                await asyncio.sleep(180)  # Check every 3 minutes
                
            except Exception as e:
                print(f"❌ Error in miner monitoring loop: {e}")
                await asyncio.sleep(15)
        
        print("👀 Miner monitoring loop stopped")
    
    async def workflow_status_monitoring(self):
        """Monitor overall workflow status and performance"""
        print("📊 Starting workflow status monitoring...")
        
        # Run migrations once at startup
        try:
            # First, ensure DONE status exists in enum
            from database.migrations.add_done_to_enum import migrate_add_done_to_enum
            print("🔄 Running enum migration (add DONE status)...")
            migrate_add_done_to_enum(self.db)
        except Exception as e:
            print(f"⚠️  Could not run enum migration: {e}")
        
        # Then run task status fix
        try:
            from database.migrations.fix_task_statuses import fix_task_statuses
            print("🔄 Running initial task status fix...")
            result = fix_task_statuses(self.db)
            if result.get('success'):
                print(f"✅ Initial status fix: {result.get('completed_count', 0)} COMPLETED, {result.get('done_count', 0)} DONE")
        except Exception as e:
            print(f"⚠️  Could not run initial status fix: {e}")
        
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
            # Query directly from PostgreSQL for accurate counts
            from database.postgresql_schema import Task, TaskStatusEnum
            from sqlalchemy import text
            
            # Use a helper function to safely get count for each status
            def safe_count_status(session, status_enum, status_name):
                """Safely count tasks by status, handling enum errors"""
                try:
                    return session.query(Task).filter(
                        Task.status == status_enum
                    ).count()
                except Exception as e:
                    # If enum value doesn't exist, rollback and return 0
                    if "InvalidTextRepresentation" in str(e) or "enum" in str(e).lower():
                        session.rollback()
                        return 0
                    # For transaction errors, rollback and retry with new session
                    if "InFailedSqlTransaction" in str(e) or "transaction" in str(e).lower():
                        session.rollback()
                        # Retry with a fresh query
                        try:
                            return session.query(Task).filter(
                                Task.status == status_enum
                            ).count()
                        except:
                            session.rollback()
                            return 0
                    raise
            
            session = self.db._get_session()
            try:
                # Get counts for each status directly from database
                # Use safe_count_status to handle enum errors gracefully
                pending_count = safe_count_status(session, TaskStatusEnum.PENDING, 'PENDING')
                distributed_count = safe_count_status(session, TaskStatusEnum.ASSIGNED, 'ASSIGNED')
                in_progress_count = safe_count_status(session, TaskStatusEnum.IN_PROGRESS, 'IN_PROGRESS')
                completed_count = safe_count_status(session, TaskStatusEnum.COMPLETED, 'COMPLETED')
                
                # DONE status (tasks evaluated and rewarded by validators)
                # Handle case where DONE might not exist in enum yet
                done_count = 0
                try:
                    done_count = safe_count_status(session, TaskStatusEnum.DONE, 'DONE')
                except Exception as e:
                    # If DONE doesn't exist in enum, count will be 0
                    session.rollback()
                    done_count = 0
                
                approved_count = safe_count_status(session, TaskStatusEnum.APPROVED, 'APPROVED')
                failed_count = safe_count_status(session, TaskStatusEnum.FAILED, 'FAILED')
                cancelled_count = safe_count_status(session, TaskStatusEnum.CANCELLED, 'CANCELLED')
                
                # Total includes all statuses
                total_tasks = (
                    pending_count + distributed_count + in_progress_count + 
                    completed_count + done_count + approved_count + 
                    failed_count + cancelled_count
                )
                
                return {
                    'timestamp': datetime.now().isoformat(),
                    'pending_tasks': pending_count,
                    'distributed_tasks': distributed_count,
                    'in_progress_tasks': in_progress_count,
                    'processing_tasks': in_progress_count,  # Alias for compatibility
                    'completed_tasks': completed_count + done_count,  # Include DONE in completed
                    'done_tasks': done_count,  # Separate count for DONE status
                    'approved_tasks': approved_count,
                    'failed_tasks': failed_count,
                    'cancelled_tasks': cancelled_count,
                    'total_tasks': total_tasks
                }
            finally:
                session.close()
            
        except Exception as e:
            print(f"❌ Error getting workflow statistics: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    async def cleanup_old_tasks(self):
        """Clean up old completed tasks and handle stale tasks with partial responses"""
        print("🧹 Starting cleanup loop...")
        
        while self.running:
            try:
                # 1. Handle stale tasks with partial responses (timeout mechanism)
                # Run this more frequently (every 15 minutes) to catch stale tasks quickly
                await self._handle_stale_tasks_with_partial_responses()
                
                await asyncio.sleep(900)  # Check every 15 minutes for stale tasks
                
            except Exception as e:
                print(f"❌ Error in cleanup loop: {e}")
                await asyncio.sleep(900)
        
        print("🧹 Cleanup loop stopped")
    
    async def cleanup_very_old_tasks(self):
        """Clean up tasks older than 7 days (runs less frequently)"""
        print("🧹 Starting very old tasks cleanup loop...")
        
        while self.running:
            try:
                # Clean up tasks older than 7 days
                cutoff_date = datetime.now() - timedelta(days=7)
                old_tasks = await self.get_old_completed_tasks(cutoff_date)
                
                for task in old_tasks:
                    if not self.running:
                        break
                    await self.archive_old_task(task)
                
                if old_tasks:
                    print(f"🧹 Cleaned up {len(old_tasks)} very old tasks")
                
                await asyncio.sleep(86400)  # Run once per day
                
            except Exception as e:
                print(f"❌ Error in very old tasks cleanup loop: {e}")
                await asyncio.sleep(86400)
        
        print("🧹 Very old tasks cleanup loop stopped")
    
    async def _handle_stale_tasks_with_partial_responses(self):
        """Mark stale tasks as completed if they have at least 1 response and are > 1 hour old"""
        try:
            # Get assigned tasks that are older than 1 hour
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            # PostgreSQL: Query stale assigned tasks
            from database.postgresql_schema import Task, TaskStatusEnum
            session = self.db._get_session()
            try:
                # Query stale assigned tasks (older than 1 hour)
                stale_assigned_tasks = session.query(Task).filter(
                    Task.status == TaskStatusEnum.ASSIGNED,
                    Task.created_at < one_hour_ago
                ).all()
                
                # Query stale pending tasks (older than 1 hour, never assigned)
                stale_pending_tasks = session.query(Task).filter(
                    Task.status == TaskStatusEnum.PENDING,
                    Task.created_at < one_hour_ago
                ).all()
                
                # Process assigned tasks with partial responses
                completed_count = 0
                completed_task_ids = []
                skipped_count = 0
                
                for task in stale_assigned_tasks:
                    # Get miner responses from task
                    miner_responses = task.miner_responses if hasattr(task, 'miner_responses') else []
                    if isinstance(miner_responses, str):
                        import json
                        try:
                            miner_responses = json.loads(miner_responses)
                        except:
                            miner_responses = []
                    response_count = len(miner_responses) if isinstance(miner_responses, list) else 0
                    
                    # If task has at least 1 response and is > 1 hour old, mark as completed
                    if response_count >= 1:
                        task.status = TaskStatusEnum.COMPLETED
                        task.completed_at = datetime.now()
                        task.updated_at = datetime.now()
                        
                        # Add completion metadata to user_metadata
                        if task.user_metadata is None:
                            task.user_metadata = {}
                        task.user_metadata['completion_reason'] = f"timeout cleanup ({response_count} response(s) after 1+ hour)"
                        task.user_metadata['actual_response_count'] = response_count
                        task.user_metadata['expected_response_count'] = len(task.assigned_miners) if task.assigned_miners else 0
                        
                        completed_count += 1
                        completed_task_ids.append(str(task.task_id))
                        print(f"⏰ Marked stale assigned task {task.task_id} as completed ({response_count} response(s) after timeout)")
                    else:
                        skipped_count += 1
                
                # Process pending tasks that were never assigned (mark as failed/incomplete)
                failed_count = 0
                failed_task_ids = []
                
                for task in stale_pending_tasks:
                    # Mark unassigned tasks as failed (they were never assigned to miners)
                    task.status = TaskStatusEnum.FAILED
                    task.updated_at = datetime.now()
                    
                    # Add failure metadata
                    if task.user_metadata is None:
                        task.user_metadata = {}
                    task.user_metadata['failure_reason'] = "task never assigned to miners after 1+ hour"
                    task.user_metadata['failure_timestamp'] = datetime.now().isoformat()
                    
                    failed_count += 1
                    failed_task_ids.append(str(task.task_id))
                    print(f"❌ Marked unassigned task {task.task_id} as failed (never assigned after 1+ hour)")
                
                # Commit all changes
                total_changes = completed_count + failed_count
                if total_changes > 0:
                    session.commit()
                    print(f"✅ Processed stale tasks: {completed_count} completed, {failed_count} failed")
                else:
                    session.commit()  # Commit even if no changes (for consistency)
                
                return {
                    'success': True,
                    'completed_count': completed_count,
                    'failed_count': failed_count,
                    'skipped_count': skipped_count,
                    'total_checked': len(stale_assigned_tasks) + len(stale_pending_tasks),
                    'completed_task_ids': completed_task_ids,
                    'failed_task_ids': failed_task_ids
                }
                    
            finally:
                session.close()
                
        except Exception as e:
            print(f"❌ Error handling stale tasks: {e}")
            import traceback
            traceback.print_exc()
    
    async def cleanup_stale_miners_loop(self):
        """Periodically clean up stale/inactive miners from the database"""
        print("🧹 Starting stale miner cleanup loop...")
        
        while self.running:
            try:
                current_time = datetime.utcnow()
                miner_timeout = 900  # 15 minutes
                
                # Get all miners from database
                # PostgreSQL: Query miner status
                from database.postgresql_schema import MinerStatus
                session = self.db._get_session()
                try:
                    miners = session.query(MinerStatus).all()
                    docs = [self.db._miner_status_to_dict(m) for m in miners]
                finally:
                    session.close()
                
                stale_miners = []
                for doc in docs:
                    miner_data = doc  # Already a dict
                    miner_id = str(miner_data.get('uid', ''))
                    
                    last_seen = miner_data.get('last_seen')
                    miner_uid = miner_data.get('uid')
                    
                    if not last_seen:
                        # No last_seen timestamp - mark as stale
                        stale_miners.append((miner_id, miner_uid, 'No last_seen timestamp'))
                        continue
                    
                    # Handle different timestamp formats
                    try:
                        if isinstance(last_seen, datetime):
                            time_diff = (current_time - last_seen).total_seconds()
                        elif isinstance(last_seen, str):
                            from dateutil import parser
                            last_seen_dt = parser.parse(last_seen)
                            time_diff = (current_time - last_seen_dt.replace(tzinfo=None)).total_seconds()
                        else:
                            # Unknown format - mark as stale
                            stale_miners.append((miner_id, miner_uid, f'Unknown timestamp format: {type(last_seen)}'))
                            continue
                        
                        # Check if miner is stale (not seen for more than timeout)
                        if time_diff > miner_timeout:
                            minutes_ago = time_diff / 60
                            stale_miners.append((miner_id, miner_uid, f'Last seen {minutes_ago:.1f} minutes ago'))
                    except Exception as e:
                        print(f"⚠️  Error checking last_seen for miner {miner_uid}: {e}")
                        stale_miners.append((miner_id, miner_uid, f'Error parsing timestamp: {e}'))
                
                # Remove stale miners from database (PostgreSQL)
                removed_count = 0
                from database.postgresql_schema import MinerStatus
                session = self.db._get_session()
                try:
                    for miner_id, miner_uid, reason in stale_miners:
                        try:
                            miner = session.query(MinerStatus).filter(MinerStatus.uid == miner_uid).first()
                            if miner:
                                session.delete(miner)
                                print(f"🗑️  Removed stale miner UID {miner_uid} ({reason})")
                                removed_count += 1
                        except Exception as e:
                            print(f"⚠️  Error removing stale miner {miner_uid}: {e}")
                    session.commit()
                finally:
                    session.close()
                
                if removed_count > 0:
                    print(f"🧹 Cleaned up {removed_count} stale miners")
                elif stale_miners:
                    print(f"⚠️  Found {len(stale_miners)} stale miners but failed to remove them")
                
                # Run cleanup every 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                # Reduce logging - only log unexpected errors (filter out known PostgreSQL/Firestore compatibility issues)
                error_str = str(e)
                if "to_dict" not in error_str and "collection" not in error_str and "'dict' object has no attribute" not in error_str:
                    print(f"⚠️ Error in stale miner cleanup: {e}")
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
            # PostgreSQL: Just delete the task (no separate archive collection)
            # In the future, we could add an archived_tasks table if needed
            from database.postgresql_schema import Task
            session = self.db._get_session()
            try:
                task_obj = session.query(Task).filter(Task.task_id == task['task_id']).first()
                if task_obj:
                    session.delete(task_obj)
                    session.commit()
            finally:
                session.close()
            
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
