#!/usr/bin/env python3
"""
Test script for Failing Endpoints Only
Focuses on endpoints that failed in previous tests
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

def get_api_keys():
    """Get API keys from database"""
    print("🔍 Retrieving API keys from database...")
    
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    try:
        db = PostgreSQLAdapter(database_url)
        session = db._get_session()
        
        api_keys = {}
        
        # Get validator API key
        validator = session.query(User).filter(
            User.role == UserRoleEnum.VALIDATOR,
            User.is_active == True
        ).first()
        
        if validator:
            api_keys['validator'] = {
                'api_key': validator.api_key,
                'uid': validator.uid,
                'email': validator.email
            }
            print(f"✅ Validator API Key found (UID: {validator.uid})")
        
        # Get miner API key
        miner = session.query(User).filter(
            User.role == UserRoleEnum.MINER,
            User.is_active == True
        ).first()
        
        if miner:
            api_keys['miner'] = {
                'api_key': miner.api_key,
                'uid': miner.uid,
                'email': miner.email
            }
            print(f"✅ Miner API Key found (UID: {miner.uid})")
        
        session.close()
        return api_keys
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_endpoint(name, method, endpoint, api_key=None, expected_status=200, **kwargs):
    """Test a single endpoint with detailed diagnostics"""
    print(f"\n{'='*80}")
    print(f"🧪 Testing: {name}")
    print(f"{'='*80}")
    print(f"   Endpoint: {method.upper()} {endpoint}")
    print(f"   URL: {BASE_URL}{endpoint}")
    print(f"   API Key: {'Provided' if api_key else 'None'}")
    if api_key:
        masked = api_key[:12] + "..." + api_key[-8:] if len(api_key) > 20 else api_key
        print(f"   Key Preview: {masked}")
    print(f"   Expected Status: {expected_status}")
    print("-" * 80)
    
    try:
        url = f"{BASE_URL}{endpoint}"
        headers = kwargs.get('headers', {})
        if api_key:
            headers['X-API-Key'] = api_key
        kwargs['headers'] = headers
        
        start_time = time.time()
        if method.upper() == "GET":
            response = requests.get(url, **kwargs, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, **kwargs, timeout=30)
        else:
            print(f"   ❌ Unsupported method")
            return False
        
        elapsed = time.time() - start_time
        
        print(f"   ⏱️  Response Time: {elapsed:.2f}s")
        print(f"   📊 Status Code: {response.status_code}")
        
        # Detailed status analysis
        if response.status_code == expected_status:
            print(f"   ✅ Status: PASS (matches expected {expected_status})")
        elif response.status_code == 401:
            print(f"   ❌ Status: UNAUTHORIZED (401)")
            print(f"   💡 Issue: Invalid or missing API key")
        elif response.status_code == 403:
            print(f"   ❌ Status: FORBIDDEN (403)")
            print(f"   💡 Issue: API key doesn't have required role/permission")
        elif response.status_code == 404:
            print(f"   ❌ Status: NOT FOUND (404)")
            print(f"   💡 Issue: Endpoint doesn't exist or path is incorrect")
        elif response.status_code == 500:
            print(f"   ❌ Status: INTERNAL SERVER ERROR (500)")
            print(f"   💡 Issue: Server-side error")
        else:
            print(f"   ⚠️  Status: {response.status_code} (unexpected)")
        
        # Parse response
        try:
            data = response.json()
            print(f"   📦 Response: JSON")
            
            if isinstance(data, dict):
                if 'detail' in data:
                    print(f"   📝 Error Detail: {data['detail']}")
                if 'evaluated_tasks' in data:
                    count = data.get('count', 0)
                    tasks = data.get('evaluated_tasks', [])
                    print(f"   📋 Evaluated Tasks: {count}")
                    if tasks:
                        print(f"   📋 Sample IDs: {tasks[:5]}")
                if 'uptime_score' in data or 'invocation_count' in data:
                    print(f"   📊 Miner Metrics:")
                    print(f"      UID: {data.get('uid', 'N/A')}")
                    print(f"      Uptime: {data.get('uptime_score', 0):.2f}")
                    print(f"      Invocation: {data.get('invocation_count', 0)}")
                    print(f"      Diversity: {data.get('diversity_score', 0):.2f}")
        except json.JSONDecodeError:
            print(f"   📄 Response: Non-JSON")
            print(f"   Preview: {response.text[:200]}")
        
        return response.status_code == expected_status
        
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Connection Error: Server not reachable at {BASE_URL}")
        return False
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout: Request took longer than 30 seconds")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Test only the failing endpoints"""
    print("\n" + "="*80)
    print("🧪 Testing Failing Endpoints Only")
    print("="*80)
    print(f"Server: {BASE_URL}")
    print("="*80)
    
    # Get API keys
    api_keys = get_api_keys()
    if not api_keys:
        print("\n❌ Could not retrieve API keys")
        return False
    
    results = []
    
    # Test 1: GET /api/v1/validator/7/evaluated_tasks
    # This was marked as FAIL but might have passed - let's test it properly
    if 'validator' in api_keys:
        validator_key = api_keys['validator']['api_key']
        validator_uid = api_keys['validator']['uid']
        results.append((
            "GET /api/v1/validator/{uid}/evaluated_tasks",
            test_endpoint(
                "Get evaluated tasks for validator",
                "GET",
                f"/api/v1/validator/{validator_uid}/evaluated_tasks",
                api_key=validator_key,
                expected_status=200
            )
        ))
    else:
        print("\n⚠️  No validator API key - skipping validator endpoints")
        results.append(("GET /api/v1/validator/7/evaluated_tasks", False))
    
    # Test 2: GET /api/v1/miners/6/metrics
    # This requires VALIDATOR auth (not miner auth!)
    if 'validator' in api_keys:
        validator_key = api_keys['validator']['api_key']
        miner_uid = api_keys.get('miner', {}).get('uid', 6) if 'miner' in api_keys else 6
        results.append((
            "GET /api/v1/miners/{uid}/metrics",
            test_endpoint(
                "Get miner metrics (requires validator auth)",
                "GET",
                f"/api/v1/miners/{miner_uid}/metrics",
                api_key=validator_key,  # Use validator key!
                expected_status=200
            )
        ))
    else:
        print("\n⚠️  No validator API key - skipping miner metrics endpoint")
        results.append(("GET /api/v1/miners/6/metrics", False))
    
    # Summary
    print("\n" + "="*80)
    print("📊 Test Results Summary")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for endpoint, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {endpoint}")
    
    print(f"\n   Results: {passed}/{total} passed ({passed*100//total if total > 0 else 0}%)")
    
    if passed == total:
        print("\n   ✅ All failing endpoints are now working!")
    else:
        print(f"\n   ⚠️  {total - passed} endpoint(s) still failing")
        print("   💡 Check the detailed output above for specific issues")
    
    print("="*80)
    
    return passed == total

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

