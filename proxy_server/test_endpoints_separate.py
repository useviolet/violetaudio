#!/usr/bin/env python3
"""
Test script for Proxy Server Endpoints - Separate Testing
Finds specific API keys and tests each endpoint individually
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

def get_specific_api_keys():
    """Query database for specific API keys needed for testing"""
    print("🔍 Querying database for API keys...")
    print("=" * 80)
    
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    try:
        db = PostgreSQLAdapter(database_url)
        session = db._get_session()
        
        api_keys = {}
        
        # Get validator API key (for validator endpoints)
        validator = session.query(User).filter(
            User.role == UserRoleEnum.VALIDATOR,
            User.is_active == True
        ).first()
        
        if validator:
            api_keys['validator'] = {
                'api_key': validator.api_key,
                'user_id': str(validator.user_id),
                'uid': validator.uid,
                'email': validator.email,
                'hotkey': validator.hotkey
            }
            print(f"✅ Found Validator API Key:")
            print(f"   UID: {validator.uid}")
            print(f"   Email: {validator.email}")
            print(f"   Hotkey: {validator.hotkey}")
            print(f"   API Key: {validator.api_key[:12]}...{validator.api_key[-8:]}")
        else:
            print("❌ No active validator found")
        
        # Get miner API key (for miner endpoints)
        miner = session.query(User).filter(
            User.role == UserRoleEnum.MINER,
            User.is_active == True
        ).first()
        
        if miner:
            api_keys['miner'] = {
                'api_key': miner.api_key,
                'user_id': str(miner.user_id),
                'uid': miner.uid,
                'email': miner.email,
                'hotkey': miner.hotkey
            }
            print(f"\n✅ Found Miner API Key:")
            print(f"   UID: {miner.uid}")
            print(f"   Email: {miner.email}")
            print(f"   Hotkey: {miner.hotkey}")
            print(f"   API Key: {miner.api_key[:12]}...{miner.api_key[-8:]}")
        else:
            print("\n❌ No active miner found")
        
        # Get client API key (for general endpoints)
        client = session.query(User).filter(
            User.role == UserRoleEnum.CLIENT,
            User.is_active == True
        ).first()
        
        if client:
            api_keys['client'] = {
                'api_key': client.api_key,
                'user_id': str(client.user_id),
                'email': client.email
            }
            print(f"\n✅ Found Client API Key:")
            print(f"   Email: {client.email}")
            print(f"   API Key: {client.api_key[:12]}...{client.api_key[-8:]}")
        else:
            print("\n❌ No active client found")
        
        session.close()
        print("\n" + "=" * 80)
        
        return api_keys
        
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_endpoint_separate(method, endpoint, description, api_key=None, expected_status=200, **kwargs):
    """Test an endpoint separately with detailed output"""
    print(f"\n{'='*80}")
    print(f"🧪 {description}")
    print(f"{'='*80}")
    print(f"   Method: {method.upper()}")
    print(f"   Endpoint: {endpoint}")
    print(f"   Full URL: {BASE_URL}{endpoint}")
    
    if api_key:
        masked_key = api_key[:12] + "..." + api_key[-8:] if len(api_key) > 20 else api_key
        print(f"   API Key: {masked_key}")
    else:
        print(f"   API Key: None (no authentication)")
    
    print(f"   Expected Status: {expected_status}")
    print("-" * 80)
    
    try:
        url = f"{BASE_URL}{endpoint}"
        
        # Add API key to headers if provided
        headers = kwargs.get('headers', {})
        if api_key:
            headers['X-API-Key'] = api_key
        kwargs['headers'] = headers
        
        # Make request
        start_time = time.time()
        # Use longer timeout for endpoints that download files or do heavy processing
        timeout = 60 if '/validator/tasks' in endpoint or '/leaderboard' in endpoint else 15
        if method.upper() == "GET":
            response = requests.get(url, **kwargs, timeout=timeout)
        elif method.upper() == "POST":
            response = requests.post(url, **kwargs, timeout=timeout)
        else:
            print(f"   ❌ Unsupported method: {method}")
            return False
        
        elapsed_time = time.time() - start_time
        
        print(f"   ⏱️  Response Time: {elapsed_time:.2f}s")
        print(f"   📊 Status Code: {response.status_code}")
        
        # Check status
        if response.status_code == expected_status:
            print(f"   ✅ Status matches expected ({expected_status})")
        else:
            print(f"   ⚠️  Status differs from expected ({expected_status})")
        
        # Parse response
        try:
            data = response.json()
            print(f"   📦 Response Type: JSON")
            
            # Print relevant data based on endpoint
            if isinstance(data, dict):
                if 'evaluated_tasks' in data:
                    count = data.get('count', 0)
                    tasks = data.get('evaluated_tasks', [])
                    print(f"   📋 Evaluated Tasks Count: {count}")
                    if tasks:
                        print(f"   📋 Sample Task IDs: {tasks[:5]}")
                
                elif 'tasks' in data:
                    tasks = data.get('tasks', [])
                    print(f"   📋 Total Tasks: {len(tasks)}")
                    if tasks:
                        tasks_with_input = sum(1 for t in tasks if t.get('input_data'))
                        print(f"   ✅ Tasks with input_data: {tasks_with_input}/{len(tasks)}")
                        # Show task types
                        task_types = {}
                        for t in tasks:
                            task_type = t.get('task_type', 'unknown')
                            task_types[task_type] = task_types.get(task_type, 0) + 1
                        print(f"   📊 Task Types: {dict(task_types)}")
                        # Show first task details
                        if tasks:
                            first_task = tasks[0]
                            print(f"   📌 First Task:")
                            print(f"      ID: {first_task.get('task_id', 'N/A')[:8]}...")
                            print(f"      Type: {first_task.get('task_type', 'N/A')}")
                            print(f"      Status: {first_task.get('status', 'N/A')}")
                            print(f"      Has input_data: {'Yes' if first_task.get('input_data') else 'No'}")
                
                elif 'leaderboard' in data:
                    leaderboard = data.get('leaderboard', [])
                    print(f"   📊 Leaderboard Entries: {len(leaderboard)}")
                    if leaderboard:
                        print(f"   🥇 Top 3 Miners:")
                        for i, miner in enumerate(leaderboard[:3], 1):
                            print(f"      {i}. UID {miner.get('uid')} - Score: {miner.get('overall_score', 0):.2f}")
                
                elif 'success' in data:
                    print(f"   ✅ Success: {data.get('success')}")
                    if 'message' in data:
                        print(f"   📝 Message: {data.get('message')}")
                
                elif 'uptime_score' in data or 'invocation_count' in data:
                    print(f"   📊 Miner Metrics:")
                    print(f"      UID: {data.get('uid', 'N/A')}")
                    print(f"      Uptime Score: {data.get('uptime_score', 0):.2f}")
                    print(f"      Invocation Count: {data.get('invocation_count', 0)}")
                    print(f"      Diversity Score: {data.get('diversity_score', 0):.2f}")
                
                else:
                    print(f"   📦 Response Keys: {list(data.keys())[:10]}")
            
            return response.status_code == expected_status
            
        except json.JSONDecodeError:
            print(f"   ⚠️  Response is not JSON")
            print(f"   📄 Response Preview: {response.text[:300]}")
            return response.status_code == expected_status
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection Error: Could not connect to {BASE_URL}")
        print(f"   💡 Make sure the proxy server is running:")
        print(f"      python proxy_server/main.py")
        print(f"      OR")
        print(f"      uvicorn proxy_server.main:app --reload --port 8000")
        return False
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout: Request took longer than 15 seconds")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Test each endpoint separately"""
    print("\n" + "="*80)
    print("🧪 Proxy Server Endpoint Tests - Separate Testing")
    print("="*80)
    print(f"Testing against: {BASE_URL}")
    print("="*80)
    
    # Get API keys from database
    api_keys = get_specific_api_keys()
    
    if not api_keys:
        print("\n❌ Could not retrieve API keys from database")
        return False
    
    results = []
    
    # Test 1: Get evaluated tasks for validator (requires validator API key)
    if 'validator' in api_keys:
        validator_key = api_keys['validator']['api_key']
        validator_uid = api_keys['validator'].get('uid', 7)
        results.append((
            f"GET /api/v1/validator/{validator_uid}/evaluated_tasks",
            test_endpoint_separate(
                "GET",
                f"/api/v1/validator/{validator_uid}/evaluated_tasks",
                f"Get evaluated tasks for validator {validator_uid}",
                api_key=validator_key,
                expected_status=200
            )
        ))
    else:
        print("\n⚠️  Skipping validator endpoints - no validator API key found")
        results.append(("GET /api/v1/validator/7/evaluated_tasks", False))
    
    # Test 2: Get tasks for evaluation (requires validator API key)
    if 'validator' in api_keys:
        validator_key = api_keys['validator']['api_key']
        results.append((
            "GET /api/v1/validator/tasks",
            test_endpoint_separate(
                "GET",
                "/api/v1/validator/tasks",
                "Get tasks for validator evaluation",
                api_key=validator_key,
                expected_status=200
            )
        ))
    else:
        results.append(("GET /api/v1/validator/tasks", False))
    
    # Test 3: Get leaderboard (might work with any API key or no auth)
    test_key = api_keys.get('client', {}).get('api_key') if 'client' in api_keys else None
    results.append((
        "GET /api/v1/leaderboard",
        test_endpoint_separate(
            "GET",
            "/api/v1/leaderboard",
            "Get leaderboard",
            api_key=test_key,
            expected_status=200
        )
    ))
    
    # Test 4: Get miner metrics (requires VALIDATOR API key, not miner!)
    # This endpoint is for validators to get miner metrics
    if 'validator' in api_keys:
        validator_key = api_keys['validator']['api_key']
        miner_uid = api_keys.get('miner', {}).get('uid', 6) if 'miner' in api_keys else 6
        results.append((
            f"GET /api/v1/miners/{miner_uid}/metrics",
            test_endpoint_separate(
                "GET",
                f"/api/v1/miners/{miner_uid}/metrics",
                f"Get metrics for miner {miner_uid} (requires validator auth)",
                api_key=validator_key,  # Use validator key, not miner key!
                expected_status=200
            )
        ))
    else:
        print("\n⚠️  Skipping miner metrics endpoint - no validator API key found")
        results.append(("GET /api/v1/miners/6/metrics", False))
    
    # Test 5: API docs (should work without auth)
    results.append((
        "GET /docs",
        test_endpoint_separate(
            "GET",
            "/docs",
            "API Documentation (Swagger UI)",
            api_key=None,
            expected_status=200
        )
    ))
    
    # Summary
    print("\n" + "="*80)
    print("📊 Test Summary")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for endpoint, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {endpoint}")
    
    print(f"\n   Total: {passed}/{total} tests passed ({passed*100//total if total > 0 else 0}%)")
    
    if passed == total:
        print("\n   ✅ All tests passed!")
    elif passed > 0:
        print(f"\n   ⚠️  {total - passed} test(s) failed")
        print("   💡 Check individual test results above for details")
    else:
        print("\n   ❌ All tests failed")
        print("   💡 Make sure the proxy server is running on the correct port")
    
    print("="*80)
    
    return passed == total

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test script error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

