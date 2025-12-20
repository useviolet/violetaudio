"""
Quick script to add validators_seen columns to tasks table
Run this when the database connection is available
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import time

def run_migration_direct(database_url: str, max_retries: int = 3, retry_delay: int = 2):
    """Run migration directly using SQLAlchemy engine without full adapter"""
    print("🔄 Running migration to add validators_seen columns...")
    
    for attempt in range(max_retries):
        try:
            print(f"   Attempt {attempt + 1}/{max_retries}...")
            
            # Create engine matching PostgreSQLAdapter's connection settings
            # Use the same connection approach as the adapter
            engine = create_engine(
                database_url,
                pool_pre_ping=True,  # Verify connections before using
                pool_size=1,  # Minimal pool for migration
                max_overflow=0,
                echo=False
            )
            
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("   ✅ Database connection established")
            
            # Create session
            Session = sessionmaker(bind=engine)
            session = Session()
            
            try:
                # Check if columns already exist
                check_query = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'tasks' 
                    AND column_name IN ('validators_seen', 'validators_seen_timestamps')
                """)
                result = session.execute(check_query)
                existing_columns = [row[0] for row in result]
                
                print(f"   Found existing columns: {existing_columns}")
                
                # Add validators_seen column if it doesn't exist
                if 'validators_seen' not in existing_columns:
                    print("   Adding validators_seen column...")
                    session.execute(text("""
                        ALTER TABLE tasks 
                        ADD COLUMN validators_seen JSONB DEFAULT '[]'::jsonb
                    """))
                    session.commit()
                    print("   ✅ Added validators_seen column")
                else:
                    print("   ✅ validators_seen column already exists")
                
                # Add validators_seen_timestamps column if it doesn't exist
                if 'validators_seen_timestamps' not in existing_columns:
                    print("   Adding validators_seen_timestamps column...")
                    session.execute(text("""
                        ALTER TABLE tasks 
                        ADD COLUMN validators_seen_timestamps JSONB DEFAULT '{}'::jsonb
                    """))
                    session.commit()
                    print("   ✅ Added validators_seen_timestamps column")
                else:
                    print("   ✅ validators_seen_timestamps column already exists")
                
                print("✅ Migration completed successfully!")
                return True
                
            except Exception as e:
                session.rollback()
                print(f"   ⚠️ Error during migration: {e}")
                raise
            finally:
                session.close()
                engine.dispose()
                
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️ Connection failed, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Migration failed after {max_retries} attempts: {e}")
                import traceback
                traceback.print_exc()
                print("\n💡 You can also run this SQL manually:")
                print("""
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS validators_seen JSONB DEFAULT '[]'::jsonb;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS validators_seen_timestamps JSONB DEFAULT '{}'::jsonb;
                """)
                return False
    
    return False

if __name__ == "__main__":
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    success = run_migration_direct(database_url)
    if not success:
        sys.exit(1)

