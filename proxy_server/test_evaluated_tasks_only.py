#!/usr/bin/env python3
"""
Test script for GET /api/v1/validator/{uid}/evaluated_tasks endpoint only
"""

import sys
import os
import requests
import json
import time

# Add project root to path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Add proxy_server to path
_proxy_server_dir = os.path.dirname(os.path.abspath(__file__))
if _proxy_server_dir not in sys.path:
    sys.path.insert(0, _proxy_server_dir)

from database.postgresql_adapter import PostgreSQLAdapter
from database.postgresql_schema import User, UserRoleEnum

# Local proxy server URL
BASE_URL = os.getenv("PROXY_SERVER_URL", "http://localhost:8000")

def get_validator_api_key():
    """Get validator API key from database"""
    print("🔍 Retrieving validator API key from database...")
    
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    try:
        db = PostgreSQLAdapter(database_url)
        session = db._get_session()
        
        validator = session.query(User).filter(
            User.role == UserRoleEnum.VALIDATOR,
            User.is_active == True
        ).first()
        
        session.close()
        
        if validator:
            print(f"✅ Validator API Key found (UID: {validator.uid})")
            return {
                'api_key': validator.api_key,
                'uid': validator.uid,
                'email': validator.email
            }
        else:
            print("❌ No active validator found")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_evaluated_tasks_endpoint():
    """Test the evaluated tasks endpoint"""
    print("\n" + "="*80)
    print("🧪 Testing: GET /api/v1/validator/{uid}/evaluated_tasks")
    print("="*80)
    
    # Get validator API key
    validator_info = get_validator_api_key()
    if not validator_info:
        print("\n❌ Cannot test - no validator API key found")
        return False
    
    validator_uid = validator_info['uid']
    api_key = validator_info['api_key']
    
    endpoint = f"/api/v1/validator/{validator_uid}/evaluated_tasks"
    url = f"{BASE_URL}{endpoint}"
    
    print(f"\n📋 Test Details:")
    print(f"   Endpoint: GET {endpoint}")
    print(f"   URL: {url}")
    print(f"   Validator UID: {validator_uid}")
    print(f"   API Key: {api_key[:12]}...{api_key[-8:]}")
    print("-" * 80)
    
    try:
        print(f"\n⏳ Making request...")
        start_time = time.time()
        
        response = requests.get(
            url,
            headers={"X-API-Key": api_key},
            timeout=30
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n📊 Response:")
        print(f"   ⏱️  Response Time: {elapsed:.2f}s")
        print(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   ✅ Status: SUCCESS")
                print(f"   📦 Response Type: JSON")
                
                if isinstance(data, dict):
                    count = data.get('count', 0)
                    tasks = data.get('evaluated_tasks', [])
                    print(f"   📋 Evaluated Tasks Count: {count}")
                    if tasks:
                        print(f"   📋 Task IDs: {tasks[:10]}")
                        if len(tasks) > 10:
                            print(f"      ... and {len(tasks) - 10} more")
                    else:
                        print(f"   ℹ️  No evaluated tasks found (this is normal if validator hasn't evaluated any tasks yet)")
                
                print(f"\n✅ Test PASSED!")
                return True
                
            except json.JSONDecodeError:
                print(f"   ⚠️  Response is not JSON")
                print(f"   📄 Response: {response.text[:200]}")
                return False
        else:
            print(f"   ❌ Status: FAILED")
            try:
                error_data = response.json()
                print(f"   📝 Error Detail: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"   📄 Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"\n   ❌ Connection Error: Server not reachable at {BASE_URL}")
        print(f"   💡 Make sure the proxy server is running")
        return False
    except requests.exceptions.Timeout:
        print(f"\n   ❌ Timeout: Request took longer than 30 seconds")
        print(f"   💡 The endpoint might be slow or hanging")
        return False
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 Evaluated Tasks Endpoint Test")
    print("="*80)
    
    success = test_evaluated_tasks_endpoint()
    
    print("\n" + "="*80)
    if success:
        print("✅ Test completed successfully!")
    else:
        print("❌ Test failed - check output above for details")
    print("="*80)
    
    sys.exit(0 if success else 1)

