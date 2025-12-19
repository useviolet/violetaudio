#!/usr/bin/env python3
"""
Check what enum values exist in the taskstatusenum
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.postgresql_adapter import PostgreSQLAdapter
from sqlalchemy import text

if __name__ == "__main__":
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    print("🔍 Checking enum values in taskstatusenum...")
    try:
        db = PostgreSQLAdapter(database_url)
        session = db._get_session()
        
        # Get all enum values
        query = text("""
            SELECT enumlabel 
            FROM pg_enum 
            WHERE enumtypid = (
                SELECT oid 
                FROM pg_type 
                WHERE typname = 'taskstatusenum'
            )
            ORDER BY enumsortorder;
        """)
        
        result = session.execute(query)
        enum_values = [row[0] for row in result]
        
        print(f"\n📋 Current enum values in taskstatusenum:")
        for value in enum_values:
            print(f"   - {value}")
        
        # Check specifically for 'done'
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
        
        print(f"\n✅ 'done' exists: {done_exists}")
        
        # Check for 'DONE' (uppercase)
        check_query_upper = text("""
            SELECT EXISTS (
                SELECT 1 
                FROM pg_enum 
                WHERE enumlabel = 'DONE' 
                AND enumtypid = (
                    SELECT oid 
                    FROM pg_type 
                    WHERE typname = 'taskstatusenum'
                )
            )
        """)
        result = session.execute(check_query_upper)
        done_upper_exists = result.scalar()
        
        print(f"✅ 'DONE' (uppercase) exists: {done_upper_exists}")
        
        session.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

