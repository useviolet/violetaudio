#!/usr/bin/env python3
"""
Test PostgreSQL connection and create schema
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from proxy_server.database.postgresql_adapter import PostgreSQLAdapter
from proxy_server.database.postgresql_schema import Base

def test_connection():
    """Test PostgreSQL connection"""
    database_url = "postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db"
    
    print("="*80)
    print("🔌 Testing PostgreSQL Connection")
    print("="*80)
    print(f"Database: {database_url.split('@')[-1]}")
    
    try:
        # Initialize adapter (this will test connection)
        adapter = PostgreSQLAdapter(database_url)
        
        print("\n✅ Connection successful!")
        
        # Create schema
        print("\n📋 Creating database schema...")
        Base.metadata.create_all(adapter.engine)
        print("✅ Schema created successfully!")
        
        # Test a simple query
        print("\n🧪 Testing database operations...")
        session = adapter._get_session()
        try:
            from proxy_server.database.postgresql_schema import Task
            count = session.query(Task).count()
            print(f"   Current tasks in database: {count}")
        except Exception as e:
            print(f"   ⚠️ Query test: {e}")
        finally:
            session.close()
        
        print("\n" + "="*80)
        print("✅ PostgreSQL connection and schema setup completed!")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)


