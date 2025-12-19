#!/usr/bin/env python3
"""
Test script for Proxy Server Endpoints - Local Testing
Tests key endpoints that validators use
"""

import requests
import json
import sys

# Local proxy server URL
BASE_URL = "http://localhost:8000"

def test_endpoint(method, endpoint, description, **kwargs):
    """Test an endpoint and print results"""
    print(f"\n{'='*80}")
    print(f"🧪 Testing: {description}")
    print(f"   {method} {endpoint}")
    print(f"{'='*80}")
    
    try:
        url = f"{BASE_URL}{endpoint}"
        
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
                        print(f"   📋 Evaluated Tasks: {data.get('count', 0)}")
                    elif 'tasks' in data:
                        print(f"   📋 Tasks: {len(data.get('tasks', []))}")
                        # Check if tasks have input_data
                        tasks = data.get('tasks', [])
                        if tasks:
                            tasks_with_input = sum(1 for t in tasks if t.get('input_data'))
                            print(f"   ✅ Tasks with input_data: {tasks_with_input}/{len(tasks)}")
                    elif 'success' in data:
                        print(f"   ✅ Success: {data.get('success')}")
                        if 'message' in data:
                            print(f"   📝 Message: {data.get('message')}")
                
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
        print(f"   💡 Make sure the proxy server is running locally on port 8000")
        return False
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout: Request took too long")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Run all endpoint tests"""
    print("\n" + "="*80)
    print("🧪 Proxy Server Endpoint Tests (Local)")
    print("="*80)
    print(f"Testing against: {BASE_URL}")
    print("="*80)
    
    results = []
    
    # Test 1: Get tasks for evaluation (validator endpoint)
    # Note: This requires authentication, so it might fail
    print("\n⚠️  Note: Some endpoints require authentication")
    print("   If tests fail with 401/403, that's expected without proper auth tokens")
    
    # Test 2: Get evaluated tasks for a validator
    # This also requires auth, but let's try it
    results.append((
        "GET /api/v1/validator/7/evaluated_tasks",
        test_endpoint(
            "GET",
            "/api/v1/validator/7/evaluated_tasks",
            "Get evaluated tasks for validator 7",
            headers={"X-API-Key": "test-key"}  # Mock auth
        )
    ))
    
    # Test 3: Health check or docs endpoint (should work without auth)
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
        print("\n   ⚠️  Some tests failed (may be due to authentication requirements)")
        print("   💡 To test authenticated endpoints, provide valid API keys")
    
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

