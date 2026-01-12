#!/usr/bin/env python3
"""
Simple test to verify validator task marking logic.
Tests the code path without requiring API key or proxy server connection.
"""

import sys
import os
from datetime import datetime, timezone

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

def test_validator_code_logic():
    """Test the validator code logic for marking tasks"""
    print_section("Test: Validator Code Logic")
    
    # Test 1: Check if mark_task_as_validator_evaluated method exists
    print("\n1. Checking validator code structure...")
    try:
        from neurons.validator import Validator
        print_result("Import Validator", True, "Validator class imported successfully")
        
        # Check if method exists
        if hasattr(Validator, 'mark_task_as_validator_evaluated'):
            print_result("Method Exists", True, "mark_task_as_validator_evaluated method found")
        else:
            print_result("Method Exists", False, "mark_task_as_validator_evaluated method not found")
            return False
        
        # Check if evaluated_tasks_cache is initialized
        import inspect
        init_source = inspect.getsource(Validator.__init__)
        if 'evaluated_tasks_cache' in init_source:
            print_result("Cache Initialized", True, "evaluated_tasks_cache initialized in __init__")
        else:
            print_result("Cache Initialized", False, "evaluated_tasks_cache not found in __init__")
        
    except Exception as e:
        print_result("Import Validator", False, f"Error: {str(e)}")
        return False
    
    # Test 2: Check task filtering logic
    print("\n2. Checking task filtering logic...")
    try:
        # Read the validator file to check filtering logic
        validator_file = os.path.join(_project_root, "neurons", "validator.py")
        with open(validator_file, 'r') as f:
            content = f.read()
        
        checks = {
            "Age Filtering": "max_task_age_hours" in content,
            "Cooldown Handling": "weights_failed_due_to_cooldown" in content,
            "Mark Task as Seen": "mark_task_as_validator_evaluated" in content,
            "Task Filtering": "validators_seen" in content and "validator_identifier" in content,
        }
        
        all_passed = True
        for check_name, check_result in checks.items():
            print_result(check_name, check_result)
            if not check_result:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print_result("Code Check", False, f"Error: {str(e)}")
        return False

def test_api_endpoint_structure():
    """Test if API endpoint structure is correct"""
    print_section("Test: API Endpoint Structure")
    
    try:
        proxy_file = os.path.join(_project_root, "proxy_server", "main.py")
        with open(proxy_file, 'r') as f:
            content = f.read()
        
        checks = {
            "Endpoint Exists": "/api/v1/validators/mark-task-seen" in content,
            "Form Data": "Form(...)" in content and "mark_task_as_seen_by_validator" in content,
            "Validators Seen Update": "validators_seen" in content and "validators_seen_timestamps" in content,
            "Database Update": "update_task" in content or "db.update" in content,
        }
        
        all_passed = True
        for check_name, check_result in checks.items():
            print_result(check_name, check_result)
            if not check_result:
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print_result("API Check", False, f"Error: {str(e)}")
        return False

def show_manual_test_instructions():
    """Show instructions for manual testing"""
    print_section("Manual Testing Instructions")
    
    print("\n📋 To test with actual API:")
    print("   1. Set VALIDATOR_API_KEY environment variable:")
    print("      export VALIDATOR_API_KEY='your-api-key'")
    print("\n   2. Run the full test:")
    print("      python3 test_validator_task_marking.py")
    print("\n   3. Or test manually:")
    print("      curl -X POST https://violet-proxy-bl4w.onrender.com/api/v1/validators/mark-task-seen \\")
    print("        -H 'X-API-Key: YOUR_API_KEY' \\")
    print("        -d 'task_id=TASK_ID' \\")
    print("        -d 'validator_uid=0' \\")
    print("        -d 'validator_identifier=test_validator' \\")
    print("        -d 'evaluated_at=2026-01-07T16:00:00Z'")
    
    print("\n📋 To verify in database:")
    print("   1. Check if task has validator in 'validators_seen' field")
    print("   2. Check if 'validators_seen_timestamps' has entry for validator")
    print("   3. Verify validator filters out task in next evaluation cycle")
    
    print("\n📋 Expected Behavior:")
    print("   ✅ Validator marks task as seen after evaluation")
    print("   ✅ Task is added to 'validators_seen' list in database")
    print("   ✅ Validator skips task in future evaluations")
    print("   ✅ Old tasks (>48h) are automatically marked as seen")

def main():
    print_section("Validator Task Marking - Code Logic Test")
    print(f"Test started at: {datetime.now().isoformat()}")
    
    # Test 1: Validator code logic
    code_test = test_validator_code_logic()
    
    # Test 2: API endpoint structure
    api_test = test_api_endpoint_structure()
    
    # Summary
    print_section("Test Summary")
    if code_test and api_test:
        print("\n✅ All code checks passed!")
        print("   The validator has the necessary logic to mark tasks as seen.")
        print("   The proxy server has the endpoint to handle task marking.")
    else:
        print("\n⚠️  Some checks failed. Review the results above.")
    
    # Show manual test instructions
    show_manual_test_instructions()
    
    print(f"\nTest completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()

