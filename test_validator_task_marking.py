#!/usr/bin/env python3
"""
Test script to verify validator can mark tasks as seen/evaluated in proxy server.
This tests the critical functionality to prevent zombie task re-evaluation.
"""

import sys
import os
import asyncio
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

def print_section(title: str):
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")

def print_result(test_name: str, success: bool, message: str = ""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"   {status}: {test_name}")
    if message:
        print(f"      {message}")

# Configuration
PROXY_SERVER_URL = "https://violet-proxy-bl4w.onrender.com"
VALIDATOR_API_KEY = os.getenv("VALIDATOR_API_KEY", "")

# Test task ID (use a real task ID from your database)
TEST_TASK_ID = None  # Will be fetched from proxy server

async def test_mark_task_seen(task_id: str, validator_uid: int = None, validator_identifier: str = "test_validator"):
    """Test marking a task as seen by validator"""
    print(f"\n🔍 Testing mark_task_seen for task: {task_id}")
    
    if not VALIDATOR_API_KEY:
        print_result("API Key Check", False, "VALIDATOR_API_KEY not set")
        return False
    
    headers = {
        "X-API-Key": VALIDATOR_API_KEY
        # Note: Don't set Content-Type for form data, httpx will set it automatically
    }
    
    # Use Form data (not JSON) as per proxy server endpoint
    payload = {
        'task_id': task_id,
        'validator_uid': validator_uid or 0,
        'validator_identifier': validator_identifier,
        'evaluated_at': datetime.now(timezone.utc).isoformat()
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{PROXY_SERVER_URL}/api/v1/validators/mark-task-seen",
                headers=headers,
                data=payload  # Use data= for form data, not json=
            )
            
            if response.status_code == 200:
                print_result("Mark Task Seen API", True, f"Status: {response.status_code}")
                data = response.json()
                print(f"      Response: {data}")
                return True
            else:
                print_result("Mark Task Seen API", False, f"Status: {response.status_code}, Response: {response.text[:200]}")
                return False
                
    except Exception as e:
        print_result("Mark Task Seen API", False, f"Error: {str(e)}")
        return False

async def get_task_from_proxy(task_id: str) -> Dict[str, Any]:
    """Get task details from proxy server"""
    try:
        headers = {}
        if VALIDATOR_API_KEY:
            headers["X-API-Key"] = VALIDATOR_API_KEY
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{PROXY_SERVER_URL}/api/v1/tasks/{task_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"   ⚠️  Failed to get task: {response.status_code}")
                return {}
    except Exception as e:
        print(f"   ⚠️  Error getting task: {e}")
        return {}

async def get_pending_tasks() -> List[Dict[str, Any]]:
    """Get pending tasks from proxy server"""
    try:
        headers = {}
        if VALIDATOR_API_KEY:
            headers["X-API-Key"] = VALIDATOR_API_KEY
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{PROXY_SERVER_URL}/api/v1/validators/tasks",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('tasks', [])
            else:
                print(f"   ⚠️  Failed to get tasks: {response.status_code}")
                return []
    except Exception as e:
        print(f"   ⚠️  Error getting tasks: {e}")
        return []

async def test_task_filtering():
    """Test if tasks are properly filtered after being marked as seen"""
    print_section("Test 3: Task Filtering After Marking")
    
    # Get tasks before marking
    print("\n📋 Getting tasks from proxy server...")
    tasks_before = await get_pending_tasks()
    print(f"   Found {len(tasks_before)} tasks")
    
    if not tasks_before:
        print_result("Task Filtering", False, "No tasks available to test")
        return False
    
    # Find a task that's not already seen
    test_task = None
    for task in tasks_before:
        validators_seen = task.get('validators_seen', [])
        if 'test_validator' not in validators_seen:
            test_task = task
            break
    
    if not test_task:
        print_result("Task Filtering", False, "All tasks already seen by test_validator")
        return False
    
    task_id = test_task.get('task_id')
    print(f"\n   Using test task: {task_id}")
    print(f"   Validators seen before: {test_task.get('validators_seen', [])}")
    
    # Mark task as seen
    print(f"\n   Marking task as seen...")
    marked = await test_mark_task_seen(task_id, validator_identifier="test_validator")
    
    if not marked:
        print_result("Task Filtering", False, "Failed to mark task as seen")
        return False
    
    # Wait a moment for database update
    await asyncio.sleep(2)
    
    # Get task again to verify it's marked
    print(f"\n   Verifying task is marked as seen...")
    task_after = await get_task_from_proxy(task_id)
    
    if task_after:
        validators_seen_after = task_after.get('validators_seen', [])
        print(f"   Validators seen after: {validators_seen_after}")
        
        if 'test_validator' in validators_seen_after:
            print_result("Task Filtering", True, "Task successfully marked as seen")
            return True
        else:
            print_result("Task Filtering", False, "Task not found in validators_seen after marking")
            return False
    else:
        print_result("Task Filtering", False, "Could not retrieve task after marking")
        return False

async def main():
    print_section("Validator Task Marking Test")
    print(f"Test started at: {datetime.now().isoformat()}")
    
    print("\n📋 Configuration:")
    print(f"   Proxy Server: {PROXY_SERVER_URL}")
    print(f"   API Key: {'✅ Set' if VALIDATOR_API_KEY else '❌ Not Set'}")
    
    # Test 1: API Key Check
    print_section("Test 1: API Key Validation")
    if not VALIDATOR_API_KEY:
        print_result("API Key", False, "VALIDATOR_API_KEY environment variable not set")
        print("\n   💡 To set: export VALIDATOR_API_KEY='your-api-key'")
        sys.exit(1)
    else:
        print_result("API Key", True, "API key is set")
    
    # Test 2: Get a test task
    print_section("Test 2: Getting Test Task")
    tasks = await get_pending_tasks()
    
    if not tasks:
        print_result("Get Tasks", False, "No tasks available from proxy server")
        print("\n   💡 Ensure proxy server is running and has tasks")
        sys.exit(1)
    
    print_result("Get Tasks", True, f"Found {len(tasks)} tasks")
    
    # Find a suitable test task (done/completed, not too old)
    test_task = None
    for task in tasks:
        status = task.get('status')
        if status in ['done', 'completed']:
            # Check age
            created_at_str = task.get('created_at')
            if created_at_str:
                try:
                    from dateutil import parser
                    created_at = parser.parse(created_at_str) if isinstance(created_at_str, str) else created_at_str
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    
                    age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                    if 1 < age_hours < 48:  # Between 1 and 48 hours old
                        test_task = task
                        break
                except:
                    pass
    
    if not test_task:
        print_result("Find Test Task", False, "No suitable test task found (need done/completed, 1-48h old)")
        print("\n   Using first available task for testing...")
        test_task = tasks[0]
    else:
        print_result("Find Test Task", True, f"Found suitable task: {test_task.get('task_id')}")
    
    task_id = test_task.get('task_id')
    print(f"\n   Task ID: {task_id}")
    print(f"   Status: {test_task.get('status')}")
    print(f"   Validators Seen: {test_task.get('validators_seen', [])}")
    
    # Test 3: Mark task as seen
    print_section("Test 3: Mark Task as Seen")
    success = await test_mark_task_seen(task_id, validator_identifier="test_validator")
    
    if success:
        # Wait and verify
        print(f"\n   Waiting 2 seconds for database update...")
        await asyncio.sleep(2)
        
        print(f"\n   Verifying task was marked...")
        task_after = await get_task_from_proxy(task_id)
        
        if task_after:
            validators_seen = task_after.get('validators_seen', [])
            print(f"   Validators seen: {validators_seen}")
            
            if 'test_validator' in validators_seen:
                print_result("Task Marking Verification", True, "Task successfully marked in database")
            else:
                print_result("Task Marking Verification", False, "Task not found in validators_seen")
        else:
            print_result("Task Marking Verification", False, "Could not retrieve task after marking")
    else:
        print_result("Task Marking", False, "Failed to mark task")
    
    # Test 4: Task filtering
    await test_task_filtering()
    
    # Summary
    print_section("Test Summary")
    print("\n📋 Key Points:")
    print("   1. Validator marks tasks as seen via API: /api/v1/validators/mark-task-seen")
    print("   2. Tasks are stored in 'validators_seen' field in database")
    print("   3. Validator filters out tasks it has already seen")
    print("   4. Old tasks (>48h) are automatically skipped and marked")
    print("\n💡 If marking fails:")
    print("   - Check VALIDATOR_API_KEY is set correctly")
    print("   - Verify proxy server is accessible")
    print("   - Check proxy server logs for errors")
    print("   - Ensure task exists in database")
    
    print(f"\nTest completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    asyncio.run(main())

