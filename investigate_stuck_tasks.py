#!/usr/bin/env python3
"""
Investigate stuck tasks that keep appearing in miner logs
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

def investigate_stuck_tasks():
    """Investigate tasks that are stuck in assigned status"""
    print_section("Stuck Tasks Investigation")
    
    # Task IDs from the logs
    stuck_task_ids = [
        "7b414944-29b0-4187-8374-4f04ec4f2b75",
        "b9d4b916-8505-457f-a60a-9507512d267f",
        "67a3bf5e-1537-4cc6-9518-f1526285dd90",
        "07228f7c-e922-4e93-8597-e177676b097b"
    ]
    
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
            for task_id in stuck_task_ids:
                print_section(f"Task: {task_id}")
                
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
                        actual_miner_count,
                        miner_responses,
                        best_response,
                        validators_seen
                    FROM tasks
                    WHERE task_id = :task_id
                """)
                
                result = conn.execute(query, {'task_id': task_id})
                task = result.fetchone()
                
                if not task:
                    print(f"❌ Task {task_id} not found in database")
                    continue
                
                (task_id_db, task_type, status, priority, created_at, updated_at,
                 distributed_at, completed_at, assigned_miners, required_count,
                 actual_count, miner_responses, best_response, validators_seen) = task
                
                # Calculate age
                if created_at:
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    age_days = (datetime.now(timezone.utc) - created_at).total_seconds() / 86400
                else:
                    age_days = 0
                
                print(f"\n📋 Task Details:")
                print(f"   Type: {task_type}")
                print(f"   Status: {status}")
                print(f"   Priority: {priority}")
                print(f"   Age: {age_days:.1f} days")
                print(f"   Created: {created_at}")
                print(f"   Updated: {updated_at}")
                print(f"   Distributed: {distributed_at}")
                print(f"   Completed: {completed_at}")
                print(f"\n👥 Assignment Details:")
                print(f"   Required Miners: {required_count}")
                print(f"   Actual Miners: {actual_count}")
                print(f"   Assigned Miners: {assigned_miners}")
                print(f"\n📊 Response Details:")
                print(f"   Miner Responses: {len(miner_responses) if miner_responses else 0}")
                if miner_responses:
                    print(f"   Response Count: {len(miner_responses)}")
                    for i, resp in enumerate(miner_responses[:3]):  # Show first 3
                        print(f"      Response {i+1}: {json.dumps(resp, indent=6)[:200]}...")
                print(f"   Best Response: {'Yes' if best_response else 'No'}")
                print(f"   Validators Seen: {len(validators_seen) if validators_seen else 0}")
                
                # Analysis
                print(f"\n🔍 Analysis:")
                if status == 'assigned' and age_days > 7:
                    print(f"   ⚠️  Task is stuck: {age_days:.1f} days old and still assigned")
                if miner_responses and len(miner_responses) > 0:
                    print(f"   ✅ Has {len(miner_responses)} miner response(s) but still assigned")
                    print(f"   ❌ Proxy server may not be updating task status after receiving responses")
                if not miner_responses or len(miner_responses) == 0:
                    print(f"   ⚠️  No miner responses recorded")
                    print(f"   ❌ Miner may be failing to submit results or proxy not recording them")
                if completed_at is None and age_days > 1:
                    print(f"   ⚠️  Task never completed despite being {age_days:.1f} days old")
        
        engine.dispose()
        
        print_section("Recommendations")
        print("\n💡 Issues Found:")
        print("   1. Tasks are stuck in 'assigned' status for weeks")
        print("   2. Tasks may have miner responses but status not updated")
        print("   3. Miner keeps reprocessing same tasks because they're still 'assigned'")
        print("\n🔧 Suggested Fixes:")
        print("   1. Filter out tasks older than 7 days in miner query")
        print("   2. Check proxy server endpoint for updating task status")
        print("   3. Add logic to mark old assigned tasks as 'failed' or 'cancelled'")
        print("   4. Verify miner result submission is working correctly")
        
    except Exception as e:
        print(f"\n❌ Error investigating stuck tasks: {e}")
        import traceback
        traceback.print_exc()

def main():
    print_section("Stuck Tasks Investigation")
    print(f"Investigation started at: {datetime.now().isoformat()}")
    
    investigate_stuck_tasks()
    
    print(f"\nInvestigation completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()


