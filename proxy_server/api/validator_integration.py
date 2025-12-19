"""
Validator Integration API for Enhanced Proxy Server
Handles communication between proxy server and validators
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from database.enhanced_schema import TaskStatus, DatabaseOperations
from database.postgresql_adapter import PostgreSQLAdapter

class ValidatorIntegrationAPI:
    def __init__(self, db):
        self.db = db
        # PostgreSQL only - no Firestore support
        self.is_postgresql = isinstance(db, PostgreSQLAdapter)
    
    async def get_tasks_for_evaluation(self, validator_uid: int = None) -> List[Dict]:
        """
        Get ALL tasks that are ready for validator evaluation (status: 'done' or 'completed').
        NOTE: This returns ALL tasks - filtering by validators_seen is done by the validator itself.
        Each validator sees all tasks, but filters out ones it has already seen.
        """
        try:
            print(f"🔍 Getting ALL tasks for evaluation (validator_uid: {validator_uid})")
            print(f"   NOTE: Returning ALL tasks - validator will filter based on its own validators_seen list")
            
            # Get tasks with 'completed' status (PostgreSQL)
            # Return ALL tasks - filtering by validators_seen is done by the validator
            # Use COMPLETED status only - this is the existing status that works
            if isinstance(self.db, PostgreSQLAdapter):
                session = None
                try:
                    from database.postgresql_schema import Task, TaskStatusEnum
                    
                    # Helper function to convert task to dict with input data
                    def task_to_dict(task):
                        task_dict = {
                            'task_id': str(task.task_id),
                            'task_type': task.task_type.value if hasattr(task.task_type, 'value') else str(task.task_type),
                            'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
                            'validators_seen': task.validators_seen if hasattr(task, 'validators_seen') and task.validators_seen else [],
                            'validators_seen_timestamps': task.validators_seen_timestamps if hasattr(task, 'validators_seen_timestamps') and task.validators_seen_timestamps else {},
                            'miner_responses': task.miner_responses or [],
                            'priority': task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
                            'created_at': task.created_at.isoformat() if task.created_at else None,
                            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                            'input_file_id': str(task.input_file_id) if task.input_file_id else None,
                            'input_text_id': str(task.input_text_id) if task.input_text_id else None,
                            'source_language': task.source_language,
                            'target_language': task.target_language,
                        }
                        
                        # Fetch input_text if input_text_id exists
                        if task.input_text_id:
                            from database.postgresql_schema import TextContent
                            text_content = session.query(TextContent).filter(
                                TextContent.content_id == task.input_text_id
                            ).first()
                            if text_content:
                                task_dict['input_text'] = {
                                    'content_id': str(text_content.content_id),
                                    'text': text_content.text,
                                    'source_language': text_content.source_language,
                                }
                        
                        # Fetch input_file if input_file_id exists
                        if task.input_file_id:
                            from database.postgresql_schema import File
                            file_obj = session.query(File).filter(
                                File.file_id == task.input_file_id
                            ).first()
                            if file_obj:
                                task_dict['input_file'] = {
                                    'file_id': str(file_obj.file_id),
                                    'file_name': file_obj.original_filename,
                                    'file_type': file_obj.content_type,
                                    'file_size': file_obj.file_size,
                                    'storage_location': file_obj.storage_location,
                                    'r2_key': file_obj.r2_key,
                                    'public_url': file_obj.public_url
                                }
                        
                        return task_dict
                    
                    # Query for COMPLETED tasks only (this status definitely exists and works)
                    session = self.db._get_session()
                    status_filter = Task.status == TaskStatusEnum.COMPLETED
                    tasks_query = session.query(Task).filter(status_filter).limit(100)
                    tasks = [task_to_dict(task) for task in tasks_query]
                finally:
                    if session:
                        try:
                            session.close()
                        except:
                            pass
            else:
                # Fallback to DatabaseOperations
                completed_tasks = DatabaseOperations.get_tasks_by_status(
                    self.db, TaskStatus.COMPLETED, limit=100
                )
                tasks = completed_tasks
            
            print(f"   📋 Found {len(tasks)} total tasks ready for evaluation")
            print(f"   ✅ Returning ALL tasks - each validator will filter based on its own validators_seen")
            
            task_list = []
            for doc in tasks:
                if self.is_postgresql:
                    task_data = doc  # Already a dict
                else:
                    task_data = doc.to_dict()
                    task_data['task_id'] = doc.id  # Use task_id for consistency
                
                # IMPORTANT: Do NOT filter here - return ALL tasks
                # The validator will filter based on validators_seen list
                # This allows each validator to see all tasks, but only evaluate ones it hasn't seen
                
                task_id = task_data.get('task_id', 'unknown')
                validators_seen = task_data.get('validators_seen', [])
                print(f"   ✅ Task {task_id} ({task_data.get('task_type', 'unknown')}) - Seen by {len(validators_seen)} validator(s): {validators_seen}")
                
                # IMPORTANT: We return ALL tasks here - filtering by validators_seen happens in the validator
                # This allows each validator to see all tasks, but only evaluate ones it hasn't seen
                
                # Get input_data from input_text or input_file
                # Priority: input_text (text content) > input_file (file content)
                
                # First, try to get input_text (for summarization, translation tasks)
                input_text = task_data.get('input_text', {})
                if input_text and isinstance(input_text, dict) and input_text.get('text'):
                    task_data['input_data'] = input_text.get('text')
                    print(f"      ✅ Using input_text ({len(str(task_data['input_data']))} chars)")
                else:
                    # Try to get input_file content (for transcription, TTS tasks)
                    input_file = task_data.get('input_file', {})
                    input_file_id = task_data.get('input_file_id')
                    
                    if input_file_id or (input_file and isinstance(input_file, dict) and input_file.get('file_id')):
                        file_id = input_file_id or input_file.get('file_id')
                        try:
                            print(f"      📁 Retrieving file content for {file_id}...")
                            
                            # Download file from R2 storage
                            try:
                                from managers.file_manager import FileManager
                                
                                # Get file_manager instance (FileManager takes db as parameter)
                                file_manager = FileManager(self.db)
                                
                                # Download file content from R2
                                file_content = await file_manager.download_file(file_id)
                                
                                if file_content:
                                    # Convert binary data to base64 string for JSON serialization
                                    import base64
                                    if isinstance(file_content, bytes):
                                        # For binary files (audio, etc.), convert to base64
                                        base64_content = base64.b64encode(file_content).decode('utf-8')
                                        task_data['input_data'] = base64_content
                                        print(f"         ✅ File content retrieved from R2 and converted to base64 ({len(file_content)} bytes -> {len(base64_content)} chars)")
                                    else:
                                        # For text files, use as-is
                                        task_data['input_data'] = file_content
                                        print(f"         ✅ File content retrieved from R2 ({len(str(file_content))} chars)")
                                else:
                                    print(f"         ❌ File content not found in R2 storage")
                                    task_data['input_data'] = None
                                    
                            except Exception as read_error:
                                print(f"         ❌ Failed to retrieve file from R2: {read_error}")
                                import traceback
                                traceback.print_exc()
                                task_data['input_data'] = None
                                    
                        except Exception as e:
                            task_id = task_data.get('task_id', 'unknown')
                            print(f"      ❌ Error retrieving file {file_id} for task {task_id}: {e}")
                            import traceback
                            traceback.print_exc()
                            task_data['input_data'] = None
                    else:
                        # No input_text or input_file found
                        print(f"      ⚠️ No input_data found in task (no input_text or input_file)")
                        task_data['input_data'] = None
                
                # Ensure we have the required fields for validator execution
                task_id = task_data.get('task_id', 'unknown')
                if not task_data.get('input_data'):
                    print(f"      ❌ Task {task_id} missing input_data, skipping...")
                    continue
                
                print(f"      ✅ Task {task_id} ready for validator execution")
                task_list.append(task_data)
            
            print(f"✅ Retrieved {len(task_list)} tasks with complete data for validator evaluation")
            return task_list
            
        except Exception as e:
            print(f"❌ Error getting tasks for evaluation: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def get_miner_responses_for_task(self, task_id: str) -> List[Dict]:
        """Get all miner responses for a specific task"""
        try:
            query = self.miner_responses_collection.where('task_id', '==', task_id)
            query = query.where('status', '==', 'completed')
            responses = query.stream()
            
            miner_responses = []
            for doc in responses:
                response_data = doc.to_dict()
                response_data['id'] = doc.id
                miner_responses.append(response_data)
            
            return miner_responses
            
        except Exception as e:
            print(f"❌ Error getting miner responses for task {task_id}: {e}")
            return []
    
    async def submit_validator_evaluation(self, task_id: str, validator_uid: int, evaluation_data: Dict):
        """Submit validator evaluation and rewards"""
        try:
            # Get task info
            task_doc = self.tasks_collection.document(task_id).get()  # Remove await
            if not task_doc.exists:
                # Raise a proper exception that will be caught and converted to 404
                raise ValueError(f"Task {task_id} not found")
            
            task_data = task_doc.to_dict()
            
            # Store evaluation results
            evaluation_doc = {
                'task_id': task_id,
                'validator_uid': validator_uid,
                'evaluation_data': evaluation_data,
                'evaluated_at': firestore.SERVER_TIMESTAMP,
                'task_type': task_data.get('task_type'),
                'miner_rewards': evaluation_data.get('miner_rewards', {}),
                'overall_score': evaluation_data.get('overall_score', 0)
            }
            
            # Store in evaluations collection
            self.evaluations_collection.document(f"{task_id}_{validator_uid}").set(evaluation_doc)  # Remove await
            
            # Update task status to 'approved'
            self.tasks_collection.document(task_id).update({  # Remove await
                'status': 'approved',
                'evaluated_by': validator_uid,
                'evaluated_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            print(f"✅ Validator {validator_uid} evaluation submitted for task {task_id}")
            
        except Exception as e:
            print(f"❌ Error submitting validator evaluation: {e}")
            raise
    
    async def notify_user_final_results(self, task_id: str, evaluation_data: Dict):
        """Notify user of final validated results"""
        try:
            # Get task info
            task_doc = await self.tasks_collection.document(task_id).get()
            if not task_doc.exists:
                return
            
            task_data = task_doc.to_dict()
            
            # Prepare final result notification
            final_result = {
                'task_id': task_id,
                'status': 'approved',
                'final_response': evaluation_data.get('best_response'),
                'validator_accuracy_score': evaluation_data.get('validator_accuracy_score'),
                'miner_rewards': evaluation_data.get('rewards', {}),
                'completed_at': firestore.SERVER_TIMESTAMP
            }
            
            # Send to user callback URL if provided
            if task_data.get('callback_url'):
                await self.send_callback_notification(task_data['callback_url'], final_result)
            
            # Store final result for user retrieval
            await self.store_final_result(task_id, final_result)
            
            print(f"📢 Final results notified for task {task_id}")
            
        except Exception as e:
            print(f"❌ Error notifying user of final results: {e}")
    
    async def send_callback_notification(self, callback_url: str, final_result: Dict):
        """Send callback notification to user"""
        try:
            # This would typically make an HTTP POST request to the callback URL
            # For now, we'll just log it
            
            print(f"📤 Callback notification sent to {callback_url}")
            print(f"   Task ID: {final_result['task_id']}")
            print(f"   Status: {final_result['status']}")
            
        except Exception as e:
            print(f"❌ Error sending callback notification: {e}")
    
    async def store_final_result(self, task_id: str, final_result: Dict):
        """Store final result for user retrieval"""
        try:
            # Store in final_results collection
            final_results_collection = self.db.collection('final_results')
            await final_results_collection.document(task_id).set(final_result)
            
            print(f"💾 Final result stored for task {task_id}")
            
        except Exception as e:
            print(f"❌ Error storing final result: {e}")
    
    async def get_validator_info(self, validator_uid: int) -> Optional[Dict]:
        """Get or create validator information"""
        try:
            doc = self.validators_collection.document(str(validator_uid)).get()  # Remove await
            if doc.exists:
                return doc.to_dict()
            
            # Create new validator info
            validator_info = {
                'validator_uid': validator_uid,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_active': firestore.SERVER_TIMESTAMP,
                'total_evaluations': 0,
                'average_evaluation_time': 0
            }
            
            self.validators_collection.document(str(validator_uid)).set(validator_info)  # Remove await
            return validator_info
            
        except Exception as e:
            print(f"❌ Error getting validator info: {e}")
            return None
    
    async def register_validator(self, validator_info: Dict) -> bool:
        """Register a new validator"""
        try:
            validator_uid = validator_info.get('uid')
            if not validator_uid:
                return False
            
            # Add registration timestamp
            validator_info['registered_at'] = firestore.SERVER_TIMESTAMP
            validator_info['last_seen'] = firestore.SERVER_TIMESTAMP
            validator_info['status'] = 'active'
            
            # Store validator info
            await self.validators_collection.document(str(validator_uid)).set(validator_info)
            
            print(f"✅ Validator {validator_uid} registered successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error registering validator: {e}")
            return False
    
    async def update_validator_status(self, validator_uid: int, status: str, **kwargs):
        """Update validator status and metadata"""
        try:
            update_data = {
                'status': status,
                'last_seen': firestore.SERVER_TIMESTAMP
            }
            update_data.update(kwargs)
            
            await self.validators_collection.document(str(validator_uid)).update(update_data)
            
            print(f"✅ Validator {validator_uid} status updated to {status}")
            
        except Exception as e:
            print(f"❌ Error updating validator status: {e}")
    
    async def get_active_validators(self) -> List[Dict]:
        """Get list of active validators"""
        try:
            query = self.validators_collection.where('status', '==', 'active')
            validators = query.stream()
            
            active_validators = []
            for doc in validators:
                validator_data = doc.to_dict()
                validator_data['id'] = doc.id
                active_validators.append(validator_data)
            
            return active_validators
            
        except Exception as e:
            print(f"❌ Error getting active validators: {e}")
            return []
    
    async def get_task_evaluation_history(self, task_id: str) -> Dict[str, Any]:
        """Get evaluation history for a specific task"""
        try:
            # Get task info
            task_doc = await self.tasks_collection.document(task_id).get()
            if not task_doc.exists:
                return {'error': 'Task not found'}
            
            task_data = task_doc.to_dict()
            
            # Get miner responses
            miner_responses = await self.get_miner_responses_for_task(task_id)
            
            # Get validator evaluation if available
            validator_evaluation = task_data.get('validator_evaluation', {})
            
            return {
                'task_id': task_id,
                'task_type': task_data.get('task_type'),
                'status': task_data.get('status'),
                'miner_responses': miner_responses,
                'validator_evaluation': validator_evaluation,
                'final_rewards': task_data.get('final_rewards', {}),
                'evaluation_timeline': {
                    'created_at': task_data.get('created_at'),
                    'distributed_at': task_data.get('distributed_at'),
                    'all_miners_completed_at': task_data.get('all_miners_completed_at'),
                    'evaluated_at': task_data.get('evaluated_at')
                }
            }
            
        except Exception as e:
            print(f"❌ Error getting task evaluation history: {e}")
            return {'error': str(e)}

    async def get_task_evaluation_status(self, task_id: str) -> Dict:
        """Get task evaluation status"""
        try:
            task_doc = self.tasks_collection.document(task_id).get()  # Remove await
            if not task_doc.exists:
                return {'error': 'Task not found'}
            
            task_data = task_doc.to_dict()
            
            # Get evaluations for this task
            query = self.evaluations_collection.where('task_id', '==', task_id)
            evaluations = query.stream()
            
            evaluation_list = []
            for doc in evaluations:
                eval_data = doc.to_dict()
                eval_data['id'] = doc.id
                evaluation_list.append(eval_data)
            
            return {
                'task_id': task_id,
                'status': task_data.get('status'),
                'evaluations': evaluation_list,
                'evaluation_count': len(evaluation_list)
            }
            
        except Exception as e:
            return {'error': f'Failed to get evaluation status: {str(e)}'}
