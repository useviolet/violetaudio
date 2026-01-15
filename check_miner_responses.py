#!/usr/bin/env python3
"""
Check miner responses in the database to see which miner_uids are actually stored
"""

import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from collections import Counter

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

def check_miner_responses():
    """Check all miner responses in the database"""
    print("\n" + "=" * 80)
    print("  MINER RESPONSES ANALYSIS")
    print("=" * 80)
    
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
            # Get all tasks with miner responses
            query = text("""
                SELECT 
                    task_id,
                    task_type,
                    status,
                    miner_responses,
                    assigned_miners,
                    created_at
                FROM tasks
                WHERE miner_responses IS NOT NULL 
                  AND jsonb_array_length(miner_responses::jsonb) > 0
                ORDER BY created_at DESC
                LIMIT 50
            """)
            
            result = conn.execute(query)
            tasks = result.fetchall()
            
            print(f"\n📊 Found {len(tasks)} tasks with miner responses\n")
            
            # Statistics
            all_miner_uids = []
            tasks_with_multiple_same_uid = []
            miner_uid_distribution = Counter()
            
            for task in tasks:
                (task_id, task_type, status, miner_responses, assigned_miners, created_at) = task
                
                # Parse miner_responses
                if isinstance(miner_responses, str):
                    try:
                        miner_responses = json.loads(miner_responses)
                    except:
                        miner_responses = []
                
                if not isinstance(miner_responses, list):
                    continue
                
                # Extract miner UIDs from responses
                response_uids = []
                for response in miner_responses:
                    if isinstance(response, dict):
                        miner_uid = response.get('miner_uid')
                        if miner_uid is not None:
                            response_uids.append(miner_uid)
                            all_miner_uids.append(miner_uid)
                            miner_uid_distribution[miner_uid] += 1
                
                # Check if multiple responses have the same UID
                if len(response_uids) != len(set(response_uids)):
                    tasks_with_multiple_same_uid.append({
                        'task_id': task_id,
                        'task_type': task_type,
                        'response_uids': response_uids,
                        'unique_uids': list(set(response_uids)),
                        'assigned_miners': assigned_miners
                    })
                
                # Show details for tasks with issues
                if len(response_uids) != len(set(response_uids)) or len(response_uids) > 3:
                    print(f"\n🔍 Task: {task_id} ({task_type})")
                    print(f"   Status: {status}")
                    print(f"   Assigned Miners: {assigned_miners}")
                    print(f"   Response UIDs: {response_uids}")
                    print(f"   Unique UIDs: {list(set(response_uids))}")
                    print(f"   Response Count: {len(response_uids)}")
                    
                    # Show each response
                    for i, response in enumerate(miner_responses):
                        if isinstance(response, dict):
                            print(f"      Response {i+1}: UID={response.get('miner_uid')}, "
                                  f"Time={response.get('submitted_at', 'N/A')}")
            
            # Print summary statistics
            print("\n" + "=" * 80)
            print("  SUMMARY STATISTICS")
            print("=" * 80)
            print(f"\n📊 Total Miner Responses Analyzed: {len(all_miner_uids)}")
            print(f"📊 Unique Miner UIDs: {len(set(all_miner_uids))}")
            print(f"📊 Tasks with Duplicate Miner UIDs: {len(tasks_with_multiple_same_uid)}")
            
            print(f"\n📈 Miner UID Distribution:")
            for uid, count in miner_uid_distribution.most_common(20):
                print(f"   UID {uid:3d}: {count:4d} responses ({count/len(all_miner_uids)*100:.1f}%)")
            
            if tasks_with_multiple_same_uid:
                print(f"\n⚠️  Tasks with Multiple Responses from Same Miner:")
                for task_info in tasks_with_multiple_same_uid[:10]:  # Show first 10
                    print(f"   Task {task_info['task_id']}: {task_info['response_uids']} "
                          f"(Unique: {task_info['unique_uids']})")
        
        engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Error checking miner responses: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_miner_responses()

