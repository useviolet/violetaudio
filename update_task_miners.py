#!/usr/bin/env python3
"""
Script to update assigned miners for a task in the database
"""

import sys
import os
from datetime import datetime

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

def update_task_miners(task_id: str, new_miners: list):
    """Update assigned miners for a task"""
    print_section(f"Updating Task Miners: {task_id}")
    print(f"Current assigned miners: Checking...")
    print(f"New assigned miners: {new_miners}")
    print(f"New count: {len(new_miners)}")
    
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
            # First, get current assigned miners
            query = text("""
                SELECT assigned_miners, actual_miner_count
                FROM tasks
                WHERE task_id = :task_id
            """)
            
            result = conn.execute(query, {'task_id': task_id})
            task = result.fetchone()
            
            if not task:
                print(f"❌ Task {task_id} not found in database")
                return False
            
            current_miners = task[0]
            current_count = task[1]
            
            print(f"   Current assigned miners: {current_miners}")
            print(f"   Current count: {current_count}")
            
            # Update the task
            # assigned_miners is integer[] type, so pass as Python list
            # psycopg2 will handle the conversion
            update_query = text("""
                UPDATE tasks
                SET 
                    assigned_miners = :assigned_miners,
                    actual_miner_count = :actual_miner_count,
                    updated_at = NOW()
                WHERE task_id = :task_id
            """)
            
            params = {
                'task_id': task_id,
                'assigned_miners': new_miners,  # Pass as Python list, psycopg2 converts to array
                'actual_miner_count': len(new_miners)
            }
            
            conn.execute(update_query, params)
            conn.commit()
            
            print(f"✅ Task updated successfully!")
            print(f"   New assigned miners: {new_miners}")
            print(f"   New count: {len(new_miners)}")
            
            return True
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error updating task: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    task_id = "8551ecf8-4729-4ea2-84ee-b6e91d8eb876"
    
    # Current miners: [2, 4, 7, 16]
    # Add miner 6: [2, 4, 6, 7, 16]
    new_miners = [2, 4, 6, 7, 16]
    
    print_section("Update Task Miners Script")
    print(f"Task ID: {task_id}")
    print(f"Adding miner UID 6 to existing assignment")
    print(f"Started at: {datetime.now().isoformat()}")
    
    success = update_task_miners(task_id, new_miners)
    
    if success:
        print(f"\n✅ Update completed at: {datetime.now().isoformat()}")
    else:
        print(f"\n❌ Update failed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()

