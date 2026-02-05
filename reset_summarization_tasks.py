#!/usr/bin/env python3
"""
Reset summarization tasks to allow them to be processed again
"""

import sys
import os
from pathlib import Path

_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from datetime import datetime

def get_database_url():
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

# All summarization task IDs from both batches
task_ids = {
    # First batch (Bobi Wine text)
    '594aefc0-6789-478c-b008-ce38ddabb5a0': 'facebook/bart-large-cnn (First Batch)',
    '90ecc2a3-59c1-48a1-88e7-a66fdea3f0ca': 'facebook/bart-base (First Batch)',
    '9d6671d9-ece0-4d57-9b7e-97ec1fa6d2ff': 'google/pegasus-xsum (First Batch)',
    '8269b54d-5aef-4cbe-a813-fc62a2f4c0ce': 't5-small (First Batch)',
    
    # Second batch (AI text)
    '9ad97f46-bd24-4062-a116-74164cb24af7': 'facebook/bart-large-cnn (Second Batch)',
    'edbda16f-cd04-4fa2-bdcd-6be0071baa70': 'facebook/bart-base (Second Batch)',
    'e31d71e1-c954-4b9c-a26e-f8c4cdde18f1': 'google/pegasus-xsum (Second Batch)',
    'a178536a-3466-4e85-a25b-ea50637309d2': 't5-small (Second Batch)'
}

def reset_task(task_id, model_name):
    """Reset a task to allow it to be processed again"""
    database_url = get_database_url()
    
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 10,
                "sslmode": "require"
            }
        )
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Get current task info
                query = text("""
                    SELECT 
                        task_id,
                        status::text,
                        assigned_miners,
                        miner_responses
                    FROM tasks
                    WHERE task_id = CAST(:task_id AS uuid)
                """)
                
                result = conn.execute(query, {'task_id': task_id})
                task = result.fetchone()
                
                if not task:
                    print(f"❌ Task {task_id} not found")
                    trans.rollback()
                    return False
                
                current_status = task[1]
                assigned_miners = task[2] or []
                miner_responses = task[3] or []
                
                print(f"\n📋 {model_name}")
                print(f"   Task ID: {task_id}")
                print(f"   Current Status: {current_status}")
                print(f"   Assigned Miners: {assigned_miners}")
                print(f"   Current Responses: {len(miner_responses)}")
                
                # Reset the task - only update columns that exist
                update_query = text("""
                    UPDATE tasks
                    SET 
                        status = CAST('ASSIGNED' AS taskstatusenum),
                        miner_responses = :empty_responses,
                        updated_at = NOW(),
                        completed_at = NULL,
                        all_miners_completed_at = NULL
                    WHERE task_id = CAST(:task_id AS uuid)
                """)
                
                conn.execute(update_query, {
                    'task_id': task_id,
                    'empty_responses': []  # Clear all responses
                })
                
                trans.commit()
                
                print(f"   ✅ Task reset successfully!")
                print(f"   New Status: ASSIGNED")
                print(f"   Responses cleared: {len(miner_responses)} → 0")
                print(f"   Assigned Miners: {assigned_miners} (still assigned)")
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"   ❌ Error resetting task: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "=" * 80)
    print("  RESET SUMMARIZATION TASKS")
    print("=" * 80)
    print("\nThis will reset all summarization tasks to ASSIGNED status")
    print("and clear their responses so miners can process them again.\n")
    
    results = {}
    success_count = 0
    fail_count = 0
    
    for task_id, model_name in task_ids.items():
        success = reset_task(task_id, model_name)
        results[task_id] = {
            'model': model_name,
            'success': success
        }
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"\n✅ Successfully reset: {success_count} tasks")
    print(f"❌ Failed to reset: {fail_count} tasks")
    
    if success_count > 0:
        print(f"\n📋 Reset Tasks:")
        for task_id, info in results.items():
            if info['success']:
                print(f"   ✅ {info['model']}: {task_id}")
    
    if fail_count > 0:
        print(f"\n❌ Failed Tasks:")
        for task_id, info in results.items():
            if not info['success']:
                print(f"   ❌ {info['model']}: {task_id}")
    
    print("\n" + "=" * 80)
    print("All reset tasks are now in ASSIGNED status and ready for processing")
    print("Miners 6 and 16 will pick them up on their next poll")
    print("=" * 80)

if __name__ == "__main__":
    main()
