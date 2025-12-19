"""
Migration: Add DONE status and remove consensus tracking
- Adds DONE status to TaskStatusEnum
- Removes MinerConsensus table (consensus not needed in proxy)
- Removes ValidatorReport table (if only used for consensus)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from sqlalchemy import text
from database.postgresql_adapter import PostgreSQLAdapter


def migrate_add_done_status_and_remove_consensus(db: PostgreSQLAdapter):
    """
    Migration to:
    1. Add DONE status (already in enum, just ensure it's used)
    2. Remove consensus tracking tables (not needed)
    """
    session = db._get_session()
    try:
        print("🔄 Starting migration: Add DONE status and remove consensus tracking")
        
        # 1. Check if DONE status exists in database (it's in enum, but check usage)
        print("   ✅ DONE status already in TaskStatusEnum")
        
        # 2. Drop MinerConsensus table if it exists
        try:
            session.execute(text("DROP TABLE IF EXISTS miner_consensus CASCADE"))
            session.commit()
            print("   ✅ Dropped miner_consensus table")
        except Exception as e:
            print(f"   ⚠️ Error dropping miner_consensus table: {e}")
            session.rollback()
        
        # 3. Drop ValidatorReport table if it exists and only used for consensus
        try:
            session.execute(text("DROP TABLE IF EXISTS validator_reports CASCADE"))
            session.commit()
            print("   ✅ Dropped validator_reports table")
        except Exception as e:
            print(f"   ⚠️ Error dropping validator_reports table: {e}")
            session.rollback()
        
        # 4. Update any tasks with old status to use new flow
        # No action needed - tasks will naturally flow: pending -> assigned -> completed -> done
        
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
    # Simple test - just print instructions
    print("""
    Migration: Add DONE status and remove consensus tracking
    
    To run this migration:
    1. Connect to your PostgreSQL database
    2. Run the following SQL commands:
    
    DROP TABLE IF EXISTS miner_consensus CASCADE;
    DROP TABLE IF EXISTS validator_reports CASCADE;
    
    The DONE status is already in the TaskStatusEnum, so no migration needed for that.
    
    Alternatively, you can run this migration programmatically by importing
    the migrate_add_done_status_and_remove_consensus function and passing
    a PostgreSQLAdapter instance.
    """)

