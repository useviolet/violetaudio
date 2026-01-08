#!/usr/bin/env python3
"""
Check database for unassigned tasks and active miners
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

def check_unassigned_tasks():
    """Check for unassigned tasks in database"""
    print_section("Unassigned Tasks Check")
    
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
            # Check for pending/unassigned tasks
            # Note: status is an enum, use CAST or check actual enum values
            query = text("""
                SELECT 
                    task_id,
                    task_type,
                    status::text as status,
                    priority::text as priority,
                    created_at,
                    updated_at,
                    assigned_miners,
                    required_miner_count,
                    actual_miner_count
                FROM tasks
                WHERE status::text IN ('pending', 'PENDING')
                ORDER BY created_at DESC
                LIMIT 50
            """)
            
            result = conn.execute(query)
            tasks = result.fetchall()
            
            if tasks:
                print(f"\n📋 Found {len(tasks)} unassigned/pending tasks:\n")
                
                for task in tasks:
                    task_id, task_type, status, priority, created_at, updated_at, assigned_miners, required_count, actual_count = task
                    
                    # Calculate age
                    if created_at:
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                        age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                    else:
                        age_hours = 0
                    
                    assigned = assigned_miners if assigned_miners else []
                    assigned_count = len(assigned) if isinstance(assigned, list) else 0
                    
                    print(f"   Task ID: {task_id}")
                    print(f"   Type: {task_type} | Status: {status} | Priority: {priority}")
                    print(f"   Age: {age_hours:.1f} hours")
                    print(f"   Required Miners: {required_count} | Assigned: {assigned_count} | Actual: {actual_count}")
                    if assigned:
                        print(f"   Assigned Miners: {assigned}")
                    print()
            else:
                print("\n✅ No unassigned/pending tasks found")
            
            # Check for tasks that should be assigned but aren't
            query2 = text("""
                SELECT 
                    COUNT(*) as count,
                    task_type::text as task_type,
                    status::text as status
                FROM tasks
                WHERE status::text IN ('pending', 'PENDING')
                GROUP BY task_type, status
                ORDER BY count DESC
            """)
            
            result2 = conn.execute(query2)
            summary = result2.fetchall()
            
            if summary:
                print("\n📊 Summary by Type and Status:")
                for count, task_type, status in summary:
                    print(f"   {task_type} ({status}): {count} tasks")
        
        engine.dispose()
        return len(tasks) if tasks else 0
        
    except Exception as e:
        print(f"\n❌ Error checking unassigned tasks: {e}")
        import traceback
        traceback.print_exc()
        return 0

def check_active_miners():
    """Check for active miners in database"""
    print_section("Active Miners Check")
    
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
            # Check for active miners (using actual schema: uid, is_serving, last_seen)
            query = text("""
                SELECT 
                    ms.uid,
                    m.hotkey,
                    ms.is_serving,
                    ms.last_seen,
                    ms.performance_score,
                    ms.assigned_task_count,
                    ms.updated_at
                FROM miner_status ms
                LEFT JOIN miners m ON ms.uid = m.uid
                WHERE ms.is_serving = true
                ORDER BY ms.last_seen DESC
                LIMIT 50
            """)
            
            result = conn.execute(query)
            miners = result.fetchall()
            
            if miners:
                print(f"\n✅ Found {len(miners)} active miners:\n")
                
                for miner in miners:
                    uid, hotkey, is_serving, last_seen, performance_score, assigned_task_count, updated_at = miner
                    
                    # Calculate time since last seen
                    if last_seen:
                        if last_seen.tzinfo is None:
                            last_seen = last_seen.replace(tzinfo=timezone.utc)
                        time_since = (datetime.now(timezone.utc) - last_seen).total_seconds() / 60
                    else:
                        time_since = None
                    
                    print(f"   Miner UID: {uid}")
                    print(f"   Hotkey: {hotkey[:30]}..." if hotkey and len(hotkey) > 30 else f"   Hotkey: {hotkey or 'N/A'}")
                    print(f"   Serving: {is_serving} | Performance: {performance_score:.2f} | Tasks: {assigned_task_count}")
                    if time_since is not None:
                        print(f"   Last Seen: {time_since:.1f} minutes ago")
                    else:
                        print(f"   Last Seen: Never")
                    print()
            else:
                print("\n⚠️  No active miners found in database")
            
            # Get summary
            query2 = text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_serving = true THEN 1 END) as serving_count,
                    COUNT(CASE WHEN is_serving = false THEN 1 END) as not_serving_count,
                    COUNT(CASE WHEN last_seen > NOW() - INTERVAL '1 hour' THEN 1 END) as recent_seen
                FROM miner_status
            """)
            
            result2 = conn.execute(query2)
            summary = result2.fetchone()
            
            if summary:
                total, serving_count, not_serving_count, recent_seen = summary
                print("\n📊 Miner Status Summary:")
                print(f"   Total Miners: {total}")
                print(f"   Serving: {serving_count}")
                print(f"   Not Serving: {not_serving_count}")
                print(f"   Recent Activity (<1h): {recent_seen}")
        
        engine.dispose()
        return len(miners) if miners else 0
        
    except Exception as e:
        print(f"\n❌ Error checking active miners: {e}")
        import traceback
        traceback.print_exc()
        return 0

def check_task_miner_mismatch():
    """Check if there are tasks that need miners but no miners are available"""
    print_section("Task-Miner Availability Check")
    
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
            # Count serving miners
            miner_query = text("""
                SELECT COUNT(*) 
                FROM miner_status 
                WHERE is_serving = true
            """)
            miner_result = conn.execute(miner_query)
            active_miner_count = miner_result.fetchone()[0]
            
            # Count tasks needing assignment
            task_query = text("""
                SELECT 
                    COUNT(*) as count,
                    SUM(required_miner_count) as total_required
                FROM tasks
                WHERE status::text IN ('pending', 'PENDING')
            """)
            task_result = conn.execute(task_query)
            task_summary = task_result.fetchone()
            
            pending_count = task_summary[0] if task_summary else 0
            total_required = task_summary[1] if task_summary and task_summary[1] else 0
            
            print(f"\n📊 Availability Analysis:")
            print(f"   Serving Miners: {active_miner_count}")
            print(f"   Pending Tasks: {pending_count}")
            print(f"   Total Miners Required: {total_required or 0}")
            
            if active_miner_count == 0:
                print(f"\n⚠️  WARNING: No serving miners available!")
                print(f"   Tasks cannot be assigned without serving miners.")
                print(f"   Check validator logs to see if miners are being reported.")
            elif pending_count > 0 and active_miner_count > 0:
                if total_required and total_required > active_miner_count:
                    print(f"\n⚠️  WARNING: Not enough miners!")
                    print(f"   Need {total_required} miners but only {active_miner_count} serving.")
                else:
                    print(f"\n✅ Sufficient miners available for pending tasks")
            elif pending_count == 0:
                print(f"\n✅ No pending tasks - all tasks are assigned or completed")
        
        engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Error checking task-miner mismatch: {e}")
        import traceback
        traceback.print_exc()

def main():
    print_section("Database Status Check")
    print(f"Check started at: {datetime.now().isoformat()}")
    
    # Check unassigned tasks
    unassigned_count = check_unassigned_tasks()
    
    # Check active miners
    active_miner_count = check_active_miners()
    
    # Check mismatch
    check_task_miner_mismatch()
    
    # Summary
    print_section("Summary")
    print(f"\n📋 Results:")
    print(f"   Unassigned Tasks: {unassigned_count}")
    print(f"   Active Miners: {active_miner_count}")
    
    if unassigned_count > 0 and active_miner_count == 0:
        print(f"\n⚠️  ISSUE: Tasks are waiting but no miners are active!")
        print(f"   Action: Check validator logs to ensure miners are being reported")
    elif unassigned_count > 0 and active_miner_count > 0:
        print(f"\n✅ Miners are available - tasks should be assigned soon")
    elif unassigned_count == 0:
        print(f"\n✅ No unassigned tasks - system is healthy")
    
    print(f"\nCheck completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()

