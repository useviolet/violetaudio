#!/usr/bin/env python3
"""
Check a specific task ID in the PostgreSQL database
"""

import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
import json

def get_database_url():
    """Get database URL from environment or use default"""
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

def print_section(title: str):
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")

def check_task(task_id: str):
    """Check details for a specific task ID"""
    print_section(f"Task Check: {task_id}")
    
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
            # Get task details
            query = text("""
                SELECT 
                    task_id,
                    task_type::text as task_type,
                    status::text as status,
                    priority::text as priority,
                    created_at,
                    updated_at,
                    distributed_at,
                    completed_at,
                    assigned_miners,
                    required_miner_count,
                    min_miner_count,
                    max_miner_count,
                    actual_miner_count,
                    miner_responses,
                    best_response,
                    validators_seen,
                    model_id
                FROM tasks
                WHERE task_id = :task_id
            """)
            
            result = conn.execute(query, {'task_id': task_id})
            task = result.fetchone()
            
            if not task:
                print(f"\n❌ Task {task_id} not found in database")
                return
            
            (task_id_db, task_type, status, priority, created_at, updated_at,
             distributed_at, completed_at, assigned_miners, required_count,
             min_count, max_count, actual_count, miner_responses, 
             best_response, validators_seen, model_id) = task
            
            # Calculate timings
            now = datetime.now(timezone.utc)
            
            if created_at:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_days = (now - created_at).total_seconds() / 86400
                age_hours = (now - created_at).total_seconds() / 3600
                age_minutes = (now - created_at).total_seconds() / 60
            else:
                age_days = 0
                age_hours = 0
                age_minutes = 0
            
            # Calculate time to distribution
            time_to_distribute = None
            if distributed_at:
                if distributed_at.tzinfo is None:
                    distributed_at = distributed_at.replace(tzinfo=timezone.utc)
                time_to_distribute = (distributed_at - created_at).total_seconds() if created_at else None
            
            # Calculate time to first response
            time_to_first_response = None
            if miner_responses and len(miner_responses) > 0 and distributed_at:
                # Try to get timestamp from first response if available
                first_response = miner_responses[0]
                if isinstance(first_response, dict) and 'timestamp' in first_response:
                    response_time = datetime.fromisoformat(first_response['timestamp'].replace('Z', '+00:00'))
                    time_to_first_response = (response_time - distributed_at).total_seconds()
                elif distributed_at:
                    # Use updated_at as proxy if response has no timestamp
                    if updated_at:
                        if updated_at.tzinfo is None:
                            updated_at = updated_at.replace(tzinfo=timezone.utc)
                        time_to_first_response = (updated_at - distributed_at).total_seconds()
            
            # Calculate time to completion
            time_to_completion = None
            if completed_at:
                if completed_at.tzinfo is None:
                    completed_at = completed_at.replace(tzinfo=timezone.utc)
                time_to_completion = (completed_at - created_at).total_seconds() if created_at else None
            
            print(f"\n📋 Task Details:")
            print(f"   Task ID: {task_id_db}")
            print(f"   Type: {task_type}")
            print(f"   Status: {status}")
            print(f"   Priority: {priority}")
            print(f"   Model ID: {model_id if model_id else 'Not specified (using default)'}")
            print(f"   Age: {age_days:.2f} days ({age_hours:.1f} hours / {age_minutes:.1f} minutes)")
            
            print(f"\n⏰ Timestamps:")
            print(f"   Created: {created_at}")
            print(f"   Updated: {updated_at}")
            print(f"   Distributed: {distributed_at}")
            print(f"   Completed: {completed_at}")
            
            print(f"\n⏱️  Timing Analysis:")
            if time_to_distribute is not None:
                print(f"   Time to Distribution: {time_to_distribute:.1f} seconds ({time_to_distribute/60:.2f} minutes)")
            else:
                print(f"   Time to Distribution: Not yet distributed")
            
            if time_to_first_response is not None:
                print(f"   Time to First Response: {time_to_first_response:.1f} seconds ({time_to_first_response/60:.2f} minutes)")
            elif miner_responses and len(miner_responses) > 0:
                print(f"   Time to First Response: Response received (timestamp not available)")
            else:
                print(f"   Time to First Response: No responses yet")
            
            if time_to_completion is not None:
                print(f"   Time to Completion: {time_to_completion:.1f} seconds ({time_to_completion/60:.2f} minutes / {time_to_completion/3600:.2f} hours)")
            else:
                print(f"   Time to Completion: Not yet completed")
            
            print(f"\n👥 Assignment Details:")
            print(f"   Required Miners: {required_count}")
            print(f"   Min Miners: {min_count}")
            print(f"   Max Miners: {max_count}")
            print(f"   Actual Miners: {actual_count}")
            if assigned_miners:
                print(f"   Assigned Miners: {assigned_miners}")
                if isinstance(assigned_miners, list):
                    print(f"   Assigned Count: {len(assigned_miners)}")
            else:
                print(f"   Assigned Miners: None")
            
            print(f"\n📊 Response Details:")
            if miner_responses:
                print(f"   Miner Responses: {len(miner_responses)} response(s)")
                for i, resp in enumerate(miner_responses):
                    print(f"      Response {i+1}:")
                    if isinstance(resp, dict):
                        print(f"         {json.dumps(resp, indent=8)}")
                    else:
                        print(f"         {resp}")
            else:
                print(f"   Miner Responses: None (0 responses)")
            
            print(f"   Best Response: {best_response if best_response else 'None'}")
            
            if validators_seen:
                print(f"   Validators Seen: {len(validators_seen)} validator(s)")
                if isinstance(validators_seen, list):
                    for i, validator in enumerate(validators_seen):
                        print(f"      Validator {i+1}: {validator}")
            else:
                print(f"   Validators Seen: None (0 validators)")
            
            # Analysis
            print(f"\n🔍 Analysis:")
            if status == 'assigned' and age_days > 7:
                print(f"   ⚠️  Task is stuck: {age_days:.1f} days old and still assigned")
            elif status == 'assigned' and age_hours > 24:
                print(f"   ⚠️  Task has been assigned for {age_hours:.1f} hours")
            
            if miner_responses and len(miner_responses) > 0:
                print(f"   ✅ Has {len(miner_responses)} miner response(s)")
                if status == 'assigned':
                    print(f"   ⚠️  Still in 'assigned' status despite having responses")
            else:
                print(f"   ⚠️  No miner responses recorded")
            
            if completed_at is None:
                if age_days > 1:
                    print(f"   ⚠️  Task never completed despite being {age_days:.1f} days old")
            else:
                print(f"   ✅ Task completed at: {completed_at}")
            
            if actual_count and required_count:
                if actual_count < required_count:
                    print(f"   ⚠️  Only {actual_count}/{required_count} miners responded")
                elif actual_count >= required_count:
                    print(f"   ✅ Sufficient miners responded ({actual_count}/{required_count})")
        
        engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Error checking task: {e}")
        import traceback
        traceback.print_exc()

def main():
    task_id = "d550c420-e1b0-41cd-a8ba-60222e86622c"
    
    print_section("Task Check Script")
    print(f"Checking task ID: {task_id}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    check_task(task_id)
    
    print(f"\n✅ Check completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()

