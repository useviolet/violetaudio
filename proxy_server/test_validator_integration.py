#!/usr/bin/env python3
"""
Test script for ValidatorIntegrationAPI
Tests the get_tasks_for_evaluation endpoint
"""

import sys
import os
import asyncio

# Add project root to path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Add proxy_server to path
_proxy_server_dir = os.path.dirname(os.path.abspath(__file__))
if _proxy_server_dir not in sys.path:
    sys.path.insert(0, _proxy_server_dir)

from database.postgresql_adapter import PostgreSQLAdapter
from api.validator_integration import ValidatorIntegrationAPI

async def test_validator_integration():
    """Test the ValidatorIntegrationAPI"""
    print("🧪 Testing ValidatorIntegrationAPI...")
    
    # Get database URL from environment or use default
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    try:
        # Initialize database adapter
        print("📦 Initializing PostgreSQL adapter...")
        db = PostgreSQLAdapter(database_url)
        print("✅ Database adapter initialized")
        
        # Initialize ValidatorIntegrationAPI
        print("📦 Initializing ValidatorIntegrationAPI...")
        validator_api = ValidatorIntegrationAPI(db)
        print("✅ ValidatorIntegrationAPI initialized")
        
        # Check if is_postgresql attribute exists
        if hasattr(validator_api, 'is_postgresql'):
            print(f"✅ is_postgresql attribute exists: {validator_api.is_postgresql}")
        else:
            print("❌ is_postgresql attribute missing!")
            return False
        
        # Test get_tasks_for_evaluation
        print("\n🔍 Testing get_tasks_for_evaluation...")
        tasks = await validator_api.get_tasks_for_evaluation(validator_uid=1)
        
        print(f"✅ Retrieved {len(tasks)} tasks for evaluation")
        
        if tasks:
            print(f"\n📋 Sample task structure:")
            sample_task = tasks[0]
            print(f"   Task ID: {sample_task.get('task_id', 'N/A')}")
            print(f"   Task Type: {sample_task.get('task_type', 'N/A')}")
            print(f"   Status: {sample_task.get('status', 'N/A')}")
            print(f"   Validators Seen: {sample_task.get('validators_seen', [])}")
            print(f"   Miner Responses: {len(sample_task.get('miner_responses', []))} responses")
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_validator_integration())
    sys.exit(0 if success else 1)

