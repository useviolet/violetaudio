"""
Migration: Add DONE status to TaskStatusEnum in PostgreSQL
"""

from sqlalchemy import text
from database.postgresql_adapter import PostgreSQLAdapter


def migrate_add_done_to_enum(db: PostgreSQLAdapter):
    """
    Migration to add DONE status to the TaskStatusEnum in PostgreSQL.
    """
    session = db._get_session()
    try:
        print("🔄 Starting migration: Add DONE to TaskStatusEnum")
        
        # Check if DONE already exists in the enum
        check_query = text("""
            SELECT EXISTS (
                SELECT 1 
                FROM pg_enum 
                WHERE enumlabel = 'done' 
                AND enumtypid = (
                    SELECT oid 
                    FROM pg_type 
                    WHERE typname = 'taskstatusenum'
                )
            )
        """)
        result = session.execute(check_query)
        done_exists = result.scalar()
        
        if done_exists:
            print("   ✅ DONE status already exists in TaskStatusEnum")
            return True
        
        # Add DONE to the enum
        try:
            # PostgreSQL requires ALTER TYPE ... ADD VALUE to be in a transaction
            # and cannot be rolled back, so we need to be careful
            session.execute(text("""
                ALTER TYPE taskstatusenum ADD VALUE IF NOT EXISTS 'done'
            """))
            session.commit()
            print("   ✅ Added DONE status to TaskStatusEnum")
        except Exception as e:
            session.rollback()
            # If it's already there (race condition), that's fine
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print("   ✅ DONE status already exists (race condition)")
            else:
                print(f"   ⚠️ Error adding DONE status: {e}")
                # Try alternative method using ALTER TYPE with IF NOT EXISTS
                try:
                    session.execute(text("""
                        DO $$ BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_enum 
                                WHERE enumlabel = 'done' 
                                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'taskstatusenum')
                            ) THEN
                                ALTER TYPE taskstatusenum ADD VALUE 'done';
                            END IF;
                        END $$;
                    """))
                    session.commit()
                    print("   ✅ Added DONE status to TaskStatusEnum (alternative method)")
                except Exception as e2:
                    session.rollback()
                    print(f"   ❌ Failed to add DONE status: {e2}")
                    return False
        
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
            'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
        )
        db = PostgreSQLAdapter(database_url)
        migrate_add_done_to_enum(db)
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        import traceback
        traceback.print_exc()
        print("\nTo run manually, connect to PostgreSQL and execute:")
        print("""
ALTER TYPE taskstatusenum ADD VALUE IF NOT EXISTS 'done';
        """)

