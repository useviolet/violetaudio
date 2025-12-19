"""
Quick script to add DONE status to TaskStatusEnum
Run this when the database connection is available
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.postgresql_adapter import PostgreSQLAdapter
from database.migrations.add_done_to_enum import migrate_add_done_to_enum

if __name__ == "__main__":
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    print("🔄 Running migration to add DONE to TaskStatusEnum...")
    try:
        db = PostgreSQLAdapter(database_url)
        success = migrate_add_done_to_enum(db)
        if success:
            print("✅ Migration completed successfully!")
        else:
            print("❌ Migration failed - check errors above")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 You can also run this SQL manually:")
        print("""
ALTER TYPE taskstatusenum ADD VALUE IF NOT EXISTS 'done';
        """)

