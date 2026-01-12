#!/usr/bin/env python3
"""
Check tasks created today and their assignment status
"""

import sys
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from urllib.parse import urlparse

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

def check_today_tasks():
    """Check tasks created today and their assignment status"""
    print_section("Today's Tasks Analysis")
    
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
            # Get today's date range (UTC)
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            print(f"\n📅 Checking tasks created between:")
            print(f"   {today_start.isoformat()}")
            print(f"   {today_end.isoformat()}")
            
            # Query tasks created today
            query = text("""
                SELECT 
                    task_id,
                    task_type::text as task_type,
                    status::text as status,
                    priority::text as priority,
                    created_at,
                    updated_at,
                    assigned_miners,
                    required_miner_count,
                    min_miner_count,
                    max_miner_count,
                    actual_miner_count,
                    distributed_at,
                    completed_at
                FROM tasks
                WHERE created_at >= :today_start 
                  AND created_at < :today_end
                ORDER BY created_at DESC
            """)
            
            result = conn.execute(query, {
                'today_start': today_start,
                'today_end': today_end
            })
            tasks = result.fetchall()
            
            if not tasks:
                print("\n✅ No tasks created today")
                return
            
            print(f"\n📋 Found {len(tasks)} task(s) created today:\n")
            
            # Categorize tasks
            assigned_tasks = []
            unassigned_tasks = []
            completed_tasks = []
            
            for task in tasks:
                (task_id, task_type, status, priority, created_at, updated_at, 
                 assigned_miners, required_count, min_count, max_count, actual_count,
                 distributed_at, completed_at) = task
                
                assigned = assigned_miners if assigned_miners else []
                assigned_count = len(assigned) if isinstance(assigned, list) else 0
                
                # Calculate age
                if created_at:
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                else:
                    age_hours = 0
                
                task_info = {
                    'task_id': task_id,
                    'task_type': task_type,
                    'status': status,
                    'priority': priority,
                    'created_at': created_at,
                    'age_hours': age_hours,
                    'assigned_miners': assigned,
                    'assigned_count': assigned_count,
                    'required_count': required_count,
                    'actual_count': actual_count,
                    'distributed_at': distributed_at,
                    'completed_at': completed_at
                }
                
                # Categorize
                if status in ['completed', 'done']:
                    completed_tasks.append(task_info)
                elif assigned_count > 0 or status == 'assigned':
                    assigned_tasks.append(task_info)
                else:
                    unassigned_tasks.append(task_info)
            
            # Print summary
            print(f"📊 Summary:")
            print(f"   Total Tasks: {len(tasks)}")
            print(f"   ✅ Assigned: {len(assigned_tasks)}")
            print(f"   ⏳ Unassigned: {len(unassigned_tasks)}")
            print(f"   ✅ Completed: {len(completed_tasks)}")
            
            # Print unassigned tasks
            if unassigned_tasks:
                print_section("⚠️  Unassigned Tasks")
                for task in unassigned_tasks:
                    print(f"\n   Task ID: {task['task_id']}")
                    print(f"   Type: {task['task_type']} | Status: {task['status']} | Priority: {task['priority']}")
                    print(f"   Age: {task['age_hours']:.2f} hours")
                    print(f"   Required Miners: {task['required_count']} | Assigned: {task['assigned_count']}")
                    print(f"   Created: {task['created_at']}")
            
            # Print assigned tasks
            if assigned_tasks:
                print_section("✅ Assigned Tasks")
                for task in assigned_tasks:
                    print(f"\n   Task ID: {task['task_id']}")
                    print(f"   Type: {task['task_type']} | Status: {task['status']}")
                    print(f"   Age: {task['age_hours']:.2f} hours")
                    print(f"   Required: {task['required_count']} | Assigned: {task['assigned_count']} | Actual: {task['actual_count']}")
                    if task['assigned_miners']:
                        print(f"   Assigned Miners: {task['assigned_miners']}")
                    if task['distributed_at']:
                        print(f"   Distributed: {task['distributed_at']}")
            
            # Print completed tasks
            if completed_tasks:
                print_section("✅ Completed Tasks")
                for task in completed_tasks[:10]:  # Show first 10
                    print(f"\n   Task ID: {task['task_id']}")
                    print(f"   Type: {task['task_type']} | Status: {task['status']}")
                    print(f"   Age: {task['age_hours']:.2f} hours")
                    if task['completed_at']:
                        print(f"   Completed: {task['completed_at']}")
                if len(completed_tasks) > 10:
                    print(f"\n   ... and {len(completed_tasks) - 10} more completed tasks")
            
            # Analysis
            print_section("Analysis")
            
            if unassigned_tasks:
                print(f"\n⚠️  ISSUE: {len(unassigned_tasks)} task(s) created today are NOT assigned")
                print(f"   Possible reasons:")
                print(f"   1. No active miners available")
                print(f"   2. Task distributor not running")
                print(f"   3. Miners at capacity")
                print(f"   4. Task requirements not met")
                
                # Check if miners are available
                miner_query = text("""
                    SELECT COUNT(*) 
                    FROM miner_status 
                    WHERE is_serving = true
                """)
                miner_result = conn.execute(miner_query)
                serving_miners = miner_result.fetchone()[0]
                
                print(f"\n   Current serving miners: {serving_miners}")
                if serving_miners == 0:
                    print(f"   ❌ No serving miners - tasks cannot be assigned!")
                else:
                    print(f"   ✅ Miners available - check task distributor logs")
            else:
                print(f"\n✅ All tasks created today have been assigned or completed")
        
        engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Error checking today's tasks: {e}")
        import traceback
        traceback.print_exc()

def main():
    print_section("Today's Tasks Assignment Check")
    print(f"Check started at: {datetime.now().isoformat()}")
    
    check_today_tasks()
    
    print(f"\nCheck completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()

