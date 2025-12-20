#!/usr/bin/env python3
"""
Test script for Proxy Server Endpoints - With Database API Keys
Queries database for API keys and uses them to test endpoints
"""

import sys
import os
import asyncio
import requests
import json

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

def get_api_keys_from_db():
    """Query database for API keys by role"""
    print("🔍 Querying database for API keys...")
    
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    try:
        db = PostgreSQLAdapter(database_url)
        session = db._get_session()
        
        api_keys = {
            'validator': [],
            'miner': [],
            'client': [],
            'admin': []
        }
        
        # Query all active users with API keys
        users = session.query(User).filter(
            User.is_active == True
        ).all()
        
        for user in users:
            role = user.role.value if hasattr(user.role, 'value') else str(user.role)
            if role in api_keys and user.api_key:
                api_keys[role].append({
                    'api_key': user.api_key,
                    'user_id': str(user.user_id),
                    'email': user.email,
                    'uid': user.uid,
                    'hotkey': user.hotkey
                })
        
        session.close()
        
        print(f"✅ Found API keys:")
        for role, keys in api_keys.items():
            print(f"   {role}: {len(keys)}")
            if keys:
                # Show first key (masked)
                first_key = keys[0]['api_key']
                masked = first_key[:8] + "..." + first_key[-4:] if len(first_key) > 12 else first_key
                print(f"      Example: {masked}")
        
        return api_keys
        
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_endpoint(method, endpoint, description, api_key=None, **kwargs):
    """Test an endpoint and print results"""
    print(f"\n{'='*80}")
    print(f"🧪 Testing: {description}")
    print(f"   {method} {endpoint}")
    if api_key:
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else api_key
        print(f"   API Key: {masked_key}")
    print(f"{'='*80}")
    
    try:
        url = f"{BASE_URL}{endpoint}"
        
        # Add API key to headers if provided
        headers = kwargs.get('headers', {})
        if api_key:
            headers['X-API-Key'] = api_key
        kwargs['headers'] = headers
        
        if method.upper() == "GET":
            response = requests.get(url, **kwargs, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, **kwargs, timeout=10)
        else:
            print(f"❌ Unsupported method: {method}")
            return False
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   ✅ Success!")
                
                # Print relevant data
                if isinstance(data, dict):
                    if 'evaluated_tasks' in data:
                        count = data.get('count', 0)
                        tasks = data.get('evaluated_tasks', [])
                        print(f"   📋 Evaluated Tasks: {count}")
                        if tasks:
                            print(f"      Sample IDs: {tasks[:3]}")
                    elif 'tasks' in data:
                        tasks = data.get('tasks', [])
                        print(f"   📋 Tasks: {len(tasks)}")
                        if tasks:
                            tasks_with_input = sum(1 for t in tasks if t.get('input_data'))
                            print(f"   ✅ Tasks with input_data: {tasks_with_input}/{len(tasks)}")
                            # Show first task type
                            if tasks:
                                print(f"   📌 First task: {tasks[0].get('task_type', 'unknown')} - {tasks[0].get('task_id', 'N/A')[:8]}...")
                    elif 'success' in data:
                        print(f"   ✅ Success: {data.get('success')}")
                        if 'message' in data:
                            print(f"   📝 Message: {data.get('message')}")
                    elif 'leaderboard' in data:
                        leaderboard = data.get('leaderboard', [])
                        print(f"   📊 Leaderboard: {len(leaderboard)} miners")
                        if leaderboard:
                            top_miner = leaderboard[0]
                            print(f"   🥇 Top miner: UID {top_miner.get('uid')} - Score: {top_miner.get('overall_score', 0):.2f}")
                
                return True
            except json.JSONDecodeError:
                print(f"   ⚠️  Response is not JSON")
                print(f"   Response: {response.text[:200]}")
                return False
        else:
            print(f"   ❌ Failed!")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"   Error: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection Error: Could not connect to {BASE_URL}")
        print(f"   💡 Make sure the proxy server is running locally")
        return False
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout: Request took too long")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Run all endpoint tests with database API keys"""
    print("\n" + "="*80)
    print("🧪 Proxy Server Endpoint Tests (With Database API Keys)")
    print("="*80)
    print(f"Testing against: {BASE_URL}")
    print("="*80)
    
    # Get API keys from database
    api_keys = get_api_keys_from_db()
    
    if not api_keys:
        print("\n❌ Could not retrieve API keys from database")
        return False
    
    results = []
    
    # Test 1: Get evaluated tasks for a validator (requires validator API key)
    validator_keys = api_keys.get('validator', [])
    if validator_keys:
        validator_key = validator_keys[0]['api_key']
        validator_uid = validator_keys[0].get('uid', 7)
        results.append((
            f"GET /api/v1/validator/{validator_uid}/evaluated_tasks",
            test_endpoint(
                "GET",
                f"/api/v1/validator/{validator_uid}/evaluated_tasks",
                f"Get evaluated tasks for validator {validator_uid}",
                api_key=validator_key
            )
        ))
    else:
        print("\n⚠️  No validator API keys found in database")
        results.append(("GET /api/v1/validator/7/evaluated_tasks", False))
    
    # Test 2: Get tasks for evaluation (requires validator API key)
    if validator_keys:
        validator_key = validator_keys[0]['api_key']
        results.append((
            "GET /api/v1/validator/tasks",
            test_endpoint(
                "GET",
                "/api/v1/validator/tasks",
                "Get tasks for validator evaluation",
                api_key=validator_key
            )
        ))
    else:
        results.append(("GET /api/v1/validator/tasks", False))
    
    # Test 3: Get leaderboard (might work without auth or with any API key)
    client_keys = api_keys.get('client', [])
    test_key = client_keys[0]['api_key'] if client_keys else None
    results.append((
        "GET /api/v1/leaderboard",
        test_endpoint(
            "GET",
            "/api/v1/leaderboard",
            "Get leaderboard",
            api_key=test_key
        )
    ))
    
    # Test 4: Get miner metrics (requires miner API key)
    miner_keys = api_keys.get('miner', [])
    if miner_keys:
        miner_key = miner_keys[0]['api_key']
        miner_uid = miner_keys[0].get('uid', 6)
        results.append((
            f"GET /api/v1/miners/{miner_uid}/metrics",
            test_endpoint(
                "GET",
                f"/api/v1/miners/{miner_uid}/metrics",
                f"Get metrics for miner {miner_uid}",
                api_key=miner_key
            )
        ))
    else:
        print("\n⚠️  No miner API keys found in database")
        results.append(("GET /api/v1/miners/6/metrics", False))
    
    # Test 5: Health check or docs endpoint (should work without auth)
    results.append((
        "GET /docs",
        test_endpoint(
            "GET",
            "/docs",
            "API Documentation (Swagger UI)"
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
    
    print(f"\n   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n   ✅ All tests passed!")
    else:
        print("\n   ⚠️  Some tests failed")
        print("   💡 Check if:")
        print("      - Proxy server is running on the correct port")
        print("      - API keys have the correct roles/permissions")
        print("      - Endpoints require specific authentication")
    
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

