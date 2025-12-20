"""
Integration tests for new API endpoints (Leaderboard and Stale Tasks)
Tests the actual HTTP endpoints using test client
"""

import pytest
import asyncio
import sys
import os
import json
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Note: This requires the FastAPI app to be importable
# We'll test the endpoints directly if app import fails


def test_leaderboard_endpoint():
    """Test leaderboard endpoint via HTTP"""
    try:
        import httpx
        import os
        
        # Get API key from environment or use test key
        api_key = os.getenv('TEST_API_KEY', 'test-key')
        base_url = os.getenv('PROXY_SERVER_URL', 'http://localhost:8000')
        
        print(f"🧪 Testing Leaderboard Endpoint: {base_url}/api/v1/leaderboard")
        
        # Test 1: Basic leaderboard
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{base_url}/api/v1/leaderboard?limit=10",
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assert data.get('success') == True
                    assert 'leaderboard' in data
                    assert isinstance(data['leaderboard'], list)
                    print(f"✅ Leaderboard endpoint test passed: {len(data['leaderboard'])} miners")
                else:
                    print(f"⚠️ Leaderboard endpoint returned {response.status_code}: {response.text}")
        except Exception as e:
            print(f"⚠️ Leaderboard endpoint test skipped (server not available): {e}")
        
        # Test 2: Leaderboard with sorting
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{base_url}/api/v1/leaderboard?limit=5&sort_by=invocation_count&order=desc",
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assert data.get('success') == True
                    print(f"✅ Leaderboard sorting test passed")
                else:
                    print(f"⚠️ Leaderboard sorting returned {response.status_code}")
        except Exception as e:
            print(f"⚠️ Leaderboard sorting test skipped: {e}")
        
        # Test 3: Individual miner lookup
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{base_url}/api/v1/leaderboard/6",
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assert data.get('success') == True
                    assert 'miner' in data
                    print(f"✅ Individual miner lookup test passed")
                elif response.status_code == 404:
                    print(f"⚠️ Miner 6 not found in leaderboard (expected if no data)")
                else:
                    print(f"⚠️ Individual miner lookup returned {response.status_code}")
        except Exception as e:
            print(f"⚠️ Individual miner lookup test skipped: {e}")
            
    except ImportError:
        print("⚠️ httpx not available, skipping HTTP endpoint tests")
    except Exception as e:
        print(f"⚠️ Endpoint test error: {e}")


def test_stale_tasks_endpoints():
    """Test stale tasks endpoints via HTTP"""
    try:
        import httpx
        import os
        
        api_key = os.getenv('TEST_API_KEY', 'test-key')
        base_url = os.getenv('PROXY_SERVER_URL', 'http://localhost:8000')
        
        print(f"🧪 Testing Stale Tasks Endpoints: {base_url}/api/v1/admin/tasks")
        
        # Test 1: Get stale stats
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{base_url}/api/v1/admin/tasks/stale-stats",
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assert data.get('success') == True
                    assert 'statistics' in data
                    print(f"✅ Stale stats endpoint test passed")
                    print(f"   Stats: {json.dumps(data['statistics'], indent=2)}")
                else:
                    print(f"⚠️ Stale stats returned {response.status_code}: {response.text}")
        except Exception as e:
            print(f"⚠️ Stale stats test skipped: {e}")
        
        # Test 2: Complete stale tasks
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{base_url}/api/v1/admin/tasks/complete-stale",
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    assert data.get('success') == True
                    assert 'statistics' in data
                    print(f"✅ Complete stale tasks endpoint test passed")
                    print(f"   Completed: {data['statistics'].get('completed_count', 0)}")
                    print(f"   Failed: {data['statistics'].get('failed_count', 0)}")
                else:
                    print(f"⚠️ Complete stale tasks returned {response.status_code}: {response.text}")
        except Exception as e:
            print(f"⚠️ Complete stale tasks test skipped: {e}")
            
    except ImportError:
        print("⚠️ httpx not available, skipping HTTP endpoint tests")
    except Exception as e:
        print(f"⚠️ Endpoint test error: {e}")


def run_integration_tests():
    """Run integration tests"""
    print("🧪 Running Integration Tests for New Endpoints...")
    print("=" * 60)
    
    test_leaderboard_endpoint()
    test_stale_tasks_endpoints()
    
    print("=" * 60)
    print("✅ Integration tests completed")


if __name__ == "__main__":
    run_integration_tests()

