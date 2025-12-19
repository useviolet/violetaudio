"""
Migration: Fix existing task statuses
- Mark tasks as COMPLETED if they have responses and meet completion criteria
- Mark tasks as DONE if they've been evaluated by validators
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from datetime import datetime, timedelta
from database.postgresql_adapter import PostgreSQLAdapter
from database.postgresql_schema import Task, TaskStatusEnum
import json


def fix_task_statuses(db: PostgreSQLAdapter):
    """
    Fix existing task statuses:
    1. Mark ASSIGNED/IN_PROGRESS tasks as COMPLETED if they have responses and meet criteria
    2. Mark COMPLETED tasks as DONE if they've been evaluated by validators
    """
    session = db._get_session()
    try:
        print("🔄 Starting task status fix...")
        
        # 1. Find tasks that should be COMPLETED
        # Get ASSIGNED and IN_PROGRESS tasks
        assigned_tasks = session.query(Task).filter(
            Task.status.in_([TaskStatusEnum.ASSIGNED, TaskStatusEnum.IN_PROGRESS])
        ).all()
        
        completed_count = 0
        skipped_count = 0
        
        for task in assigned_tasks:
            # Get miner responses
            miner_responses = task.miner_responses or []
            if isinstance(miner_responses, str):
                try:
                    miner_responses = json.loads(miner_responses)
                except:
                    miner_responses = []
            
            if not isinstance(miner_responses, list):
                miner_responses = []
            
            response_count = len(miner_responses)
            assigned_count = len(task.assigned_miners) if task.assigned_miners else 0
            min_miner_count = task.min_miner_count or 1
            
            # Check task age
            task_age_seconds = (datetime.now() - task.created_at).total_seconds() if task.created_at else 0
            task_age_hours = task_age_seconds / 3600
            
            # Check if task should be completed
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
                task.status = TaskStatusEnum.COMPLETED
                task.completed_at = datetime.now()
                task.updated_at = datetime.now()
                
                # Add completion metadata
                if task.user_metadata is None:
                    task.user_metadata = {}
                task.user_metadata['completion_reason'] = completion_reason
                task.user_metadata['actual_response_count'] = response_count
                task.user_metadata['expected_response_count'] = assigned_count
                task.user_metadata['status_fixed_at'] = datetime.now().isoformat()
                
                completed_count += 1
                print(f"   ✅ Marked task {task.task_id} as COMPLETED: {completion_reason}")
            else:
                skipped_count += 1
        
        # 2. Find COMPLETED tasks that should be DONE (evaluated by validators)
        completed_tasks = session.query(Task).filter(
            Task.status == TaskStatusEnum.COMPLETED
        ).all()
        
        done_count = 0
        
        for task in completed_tasks:
            # Check if task has been seen by validators
            validators_seen = task.validators_seen or []
            if isinstance(validators_seen, str):
                try:
                    validators_seen = json.loads(validators_seen)
                except:
                    validators_seen = []
            
            if not isinstance(validators_seen, list):
                validators_seen = []
            
            # If task has been seen by at least one validator, mark as DONE
            if len(validators_seen) > 0:
                task.status = TaskStatusEnum.DONE
                task.updated_at = datetime.now()
                
                # Add done metadata
                if task.user_metadata is None:
                    task.user_metadata = {}
                task.user_metadata['done_reason'] = f"evaluated by {len(validators_seen)} validator(s)"
                task.user_metadata['validators_seen'] = validators_seen
                task.user_metadata['status_fixed_at'] = datetime.now().isoformat()
                
                done_count += 1
                print(f"   ✅ Marked task {task.task_id} as DONE: evaluated by {len(validators_seen)} validator(s)")
        
        # Commit all changes
        if completed_count > 0 or done_count > 0:
            session.commit()
            print(f"\n✅ Status fix completed:")
            print(f"   - Marked {completed_count} tasks as COMPLETED")
            print(f"   - Marked {done_count} tasks as DONE")
            print(f"   - Skipped {skipped_count} tasks (don't meet completion criteria)")
        else:
            print(f"\n✅ No tasks needed status updates")
            print(f"   - Skipped {skipped_count} tasks (don't meet completion criteria)")
        
        return {
            'success': True,
            'completed_count': completed_count,
            'done_count': done_count,
            'skipped_count': skipped_count
        }
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error fixing task statuses: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


if __name__ == "__main__":
    import os
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    print("🔄 Running task status fix...")
    try:
        db = PostgreSQLAdapter(database_url)
        result = fix_task_statuses(db)
        if result.get('success'):
            print("✅ Task status fix completed successfully!")
        else:
            print(f"❌ Task status fix failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

