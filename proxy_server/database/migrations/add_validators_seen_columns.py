"""
Migration: Add validators_seen columns to tasks table
- Adds validators_seen (ARRAY of Integers) column
- Adds validators_seen_timestamps (JSON) column
"""

from sqlalchemy import text
from database.postgresql_adapter import PostgreSQLAdapter


def migrate_add_validators_seen_columns(db: PostgreSQLAdapter):
    """
    Migration to add validators_seen columns to tasks table.
    These columns track which validators have processed a task to prevent duplicate rewards.
    """
    session = db._get_session()
    try:
        print("🔄 Starting migration: Add validators_seen columns to tasks table")
        
        # Check if columns already exist
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tasks' 
            AND column_name IN ('validators_seen', 'validators_seen_timestamps')
        """)
        result = session.execute(check_query)
        existing_columns = [row[0] for row in result]
        
        # Add validators_seen column if it doesn't exist
        if 'validators_seen' not in existing_columns:
            try:
                session.execute(text("""
                    ALTER TABLE tasks 
                    ADD COLUMN validators_seen JSONB DEFAULT '[]'::jsonb
                """))
                session.commit()
                print("   ✅ Added validators_seen column")
            except Exception as e:
                session.rollback()
                print(f"   ⚠️ Error adding validators_seen column: {e}")
        else:
            print("   ✅ validators_seen column already exists")
        
        # Add validators_seen_timestamps column if it doesn't exist
        if 'validators_seen_timestamps' not in existing_columns:
            try:
                session.execute(text("""
                    ALTER TABLE tasks 
                    ADD COLUMN validators_seen_timestamps JSONB DEFAULT '{}'::jsonb
                """))
                session.commit()
                print("   ✅ Added validators_seen_timestamps column")
            except Exception as e:
                session.rollback()
                print(f"   ⚠️ Error adding validators_seen_timestamps column: {e}")
        else:
            print("   ✅ validators_seen_timestamps column already exists")
        
        print("✅ Migration completed successfully")
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
    
    try:
        database_url = os.getenv(
            'DATABASE_URL',
            'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vte5s738uemkg-a.oregon-postgres.render.com/violet_db'
        )
        db = PostgreSQLAdapter(database_url)
        migrate_add_validators_seen_columns(db)
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        import traceback
        traceback.print_exc()
        print("\nTo run manually, connect to PostgreSQL and execute:")
        print("""
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS validators_seen JSONB DEFAULT '[]'::jsonb;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS validators_seen_timestamps JSONB DEFAULT '{}'::jsonb;
        """)

