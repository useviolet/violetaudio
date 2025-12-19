#!/usr/bin/env python3
"""
Test script for ValidatorIntegrationAPI - Local Testing
Tests the get_tasks_for_evaluation endpoint with input_data retrieval
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
    """Test the ValidatorIntegrationAPI with input_data retrieval"""
    print("🧪 Testing ValidatorIntegrationAPI (Local)...")
    print("=" * 80)
    
    # Get database URL from environment or use default
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    try:
        # Initialize database adapter
        print("\n📦 Step 1: Initializing PostgreSQL adapter...")
        db = PostgreSQLAdapter(database_url)
        print("✅ Database adapter initialized")
        
        # Initialize ValidatorIntegrationAPI
        print("\n📦 Step 2: Initializing ValidatorIntegrationAPI...")
        validator_api = ValidatorIntegrationAPI(db)
        print("✅ ValidatorIntegrationAPI initialized")
        
        # Check if is_postgresql attribute exists
        if hasattr(validator_api, 'is_postgresql'):
            print(f"✅ is_postgresql attribute: {validator_api.is_postgresql}")
        else:
            print("❌ is_postgresql attribute missing!")
            return False
        
        # Test get_tasks_for_evaluation
        print("\n🔍 Step 3: Testing get_tasks_for_evaluation...")
        print("-" * 80)
        tasks = await validator_api.get_tasks_for_evaluation(validator_uid=1)
        
        print(f"\n✅ Retrieved {len(tasks)} tasks for evaluation")
        
        if tasks:
            print(f"\n📋 Task Details:")
            print("=" * 80)
            for i, task in enumerate(tasks[:3], 1):  # Show first 3 tasks
                print(f"\n📌 Task {i}:")
                print(f"   Task ID: {task.get('task_id', 'N/A')}")
                print(f"   Task Type: {task.get('task_type', 'N/A')}")
                print(f"   Status: {task.get('status', 'N/A')}")
                print(f"   Validators Seen: {task.get('validators_seen', [])}")
                print(f"   Miner Responses: {len(task.get('miner_responses', []))} responses")
                
                # Check input_data
                input_data = task.get('input_data')
                if input_data:
                    if isinstance(input_data, str):
                        data_length = len(input_data)
                        data_preview = input_data[:100] if len(input_data) > 100 else input_data
                        print(f"   ✅ Input Data: {data_length} chars")
                        print(f"      Preview: {data_preview}...")
                    else:
                        print(f"   ✅ Input Data: {type(input_data).__name__} ({len(str(input_data))} chars)")
                else:
                    print(f"   ❌ Input Data: MISSING")
                
                # Check input_file and input_text
                if task.get('input_file'):
                    print(f"   📁 Input File: {task.get('input_file', {}).get('file_name', 'N/A')}")
                if task.get('input_text'):
                    print(f"   📝 Input Text: {len(task.get('input_text', {}).get('text', ''))} chars")
                
                print("-" * 80)
            
            # Summary statistics
            print(f"\n📊 Summary Statistics:")
            print("=" * 80)
            tasks_with_input = sum(1 for t in tasks if t.get('input_data'))
            tasks_without_input = len(tasks) - tasks_with_input
            
            print(f"   Total Tasks: {len(tasks)}")
            print(f"   ✅ Tasks with input_data: {tasks_with_input}")
            print(f"   ❌ Tasks without input_data: {tasks_without_input}")
            
            # Task type breakdown
            task_types = {}
            for task in tasks:
                task_type = task.get('task_type', 'unknown')
                task_types[task_type] = task_types.get(task_type, 0) + 1
            
            print(f"\n   Task Types:")
            for task_type, count in task_types.items():
                print(f"      - {task_type}: {count}")
        else:
            print("⚠️  No tasks found for evaluation")
            print("   This might be normal if there are no COMPLETED tasks in the database")
        
        print("\n" + "=" * 80)
        print("✅ All tests completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 ValidatorIntegrationAPI Local Test")
    print("=" * 80)
    success = asyncio.run(test_validator_integration())
    print("\n" + "=" * 80)
    sys.exit(0 if success else 1)

