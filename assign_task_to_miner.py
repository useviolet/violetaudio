#!/usr/bin/env python3
"""
Assign a task to a specific miner UID
Usage: python assign_task_to_miner.py <task_id> <miner_uid>
       python assign_task_to_miner.py 9e9c07dc-c482-49f4-b267-d17a1515d08b 6
"""

import sys
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Database connection
database_url = os.getenv(
    'DATABASE_URL',
    'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
)

def assign_task_to_miner(task_id: str, miner_uid: int):
    """Assign a task to a specific miner UID"""
    print("\n" + "=" * 80)
    print("  ASSIGN TASK TO MINER")
    print("=" * 80)
    
    print(f"\n📋 Task ID: {task_id}")
    print(f"👷 Miner UID: {miner_uid}")
    
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            "sslmode": "require"
        }
    )
    
    try:
        with engine.connect() as conn:
            # First, check if task exists and get current assignment
            check_query = text("""
                SELECT task_id, status::text, assigned_miners, actual_miner_count, task_type::text
                FROM tasks
                WHERE task_id = CAST(:task_id AS uuid)
            """)
            result = conn.execute(check_query, {'task_id': task_id})
            task = result.fetchone()
            
            if not task:
                print(f"\n❌ Task {task_id} not found in database")
                return False
            
            print(f"\n✅ Task found:")
            print(f"   Task Type: {task[4]}")
            print(f"   Current Status: {task[1]}")
            print(f"   Current Assigned Miners: {task[2] or []}")
            print(f"   Current Miner Count: {task[3] or 0}")
            
            # Get current assigned miners list
            current_miners = task[2] if task[2] else []
            
            # Check if miner is already assigned
            if miner_uid in current_miners:
                print(f"\n⚠️  Miner UID {miner_uid} is already assigned to this task")
                return True
            
            # Add miner to the list
            new_miners = list(current_miners) + [miner_uid]
            new_count = len(new_miners)
            
            # Update task assignment
            update_query = text("""
                UPDATE tasks
                SET assigned_miners = :miners,
                    actual_miner_count = :count,
                    status = CAST('ASSIGNED' AS taskstatusenum),
                    updated_at = NOW()
                WHERE task_id = CAST(:task_id AS uuid)
            """)
            
            conn.execute(update_query, {
                'miners': new_miners,
                'count': new_count,
                'task_id': task_id
            })
            conn.commit()
            
            print(f"\n✅ Task assigned successfully!")
            print(f"   Updated Assigned Miners: {new_miners}")
            print(f"   Updated Miner Count: {new_count}")
            print(f"   Status changed to: ASSIGNED")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Error assigning task: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    # Get task_id and miner_uid from command line arguments
    if len(sys.argv) < 3:
        print("\n❌ Usage: python assign_task_to_miner.py <task_id> <miner_uid>")
        print("\n   Example:")
        print("   python assign_task_to_miner.py 9e9c07dc-c482-49f4-b267-d17a1515d08b 6")
        sys.exit(1)
    
    task_id = sys.argv[1]
    try:
        miner_uid = int(sys.argv[2])
    except ValueError:
        print(f"\n❌ Error: miner_uid must be an integer, got: {sys.argv[2]}")
        sys.exit(1)
    
    success = assign_task_to_miner(task_id, miner_uid)
    
    if success:
        print(f"\n✅ Assignment completed successfully!")
        print(f"\n   The miner will process this task on its next poll.")
    else:
        print(f"\n❌ Assignment failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
