"""
Quick script to fix existing task statuses
Run this to update tasks that should be COMPLETED or DONE
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.postgresql_adapter import PostgreSQLAdapter
from database.migrations.fix_task_statuses import fix_task_statuses

if __name__ == "__main__":
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
            print(f"   - {result.get('completed_count', 0)} tasks marked as COMPLETED")
            print(f"   - {result.get('done_count', 0)} tasks marked as DONE")
        else:
            print(f"❌ Task status fix failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

