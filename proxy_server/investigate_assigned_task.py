#!/usr/bin/env python3
"""
Get detailed information about assigned tasks and investigate why miner isn't processing them
"""

import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

import firebase_admin
from firebase_admin import credentials, firestore
import requests

def init_firebase():
    """Initialize Firebase"""
    cred_path = Path(__file__).parent / "db" / "violet.json"
    if not cred_path.exists():
        print(f"❌ Firebase credentials not found at {cred_path}")
        return None
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(str(cred_path))
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

def get_assigned_task_details(db, task_id):
    """Get complete details of an assigned task"""
    print(f"\n📋 Getting details for task: {task_id}")
    print("="*80)
    
    task_ref = db.collection('tasks').document(task_id)
    task_doc = task_ref.get()
    
    if not task_doc.exists:
        print(f"❌ Task {task_id} not found in database")
        return None
    
    task_data = task_doc.to_dict()
    
    # Print all task details
    print(f"\n🔍 Task Information:")
    print(f"   Task ID: {task_id}")
    print(f"   Type: {task_data.get('task_type', 'unknown')}")
    print(f"   Status: {task_data.get('status', 'unknown')}")
    print(f"   Priority: {task_data.get('priority', 'unknown')}")
    print(f"   Source Language: {task_data.get('source_language', 'unknown')}")
    print(f"   Created At: {task_data.get('created_at', 'unknown')}")
    print(f"   Distributed At: {task_data.get('distributed_at', 'unknown')}")
    print(f"   Updated At: {task_data.get('updated_at', 'unknown')}")
    
    # Assigned miners
    assigned_miners = task_data.get('assigned_miners', [])
    print(f"\n👷 Assigned Miners: {assigned_miners}")
    
    # Task assignments
    task_assignments = task_data.get('task_assignments', [])
    print(f"\n📝 Task Assignments ({len(task_assignments)}):")
    for i, assignment in enumerate(task_assignments, 1):
        print(f"   {i}. Miner UID: {assignment.get('miner_uid', 'unknown')}")
        print(f"      Status: {assignment.get('status', 'unknown')}")
        print(f"      Assigned At: {assignment.get('assigned_at', 'unknown')}")
        print(f"      Started At: {assignment.get('started_at', 'unknown')}")
        print(f"      Completed At: {assignment.get('completed_at', 'unknown')}")
    
    # Miner responses
    miner_responses = task_data.get('miner_responses', [])
    print(f"\n📤 Miner Responses ({len(miner_responses)}):")
    for i, response in enumerate(miner_responses, 1):
        print(f"   {i}. Miner UID: {response.get('miner_uid', 'unknown')}")
        print(f"      Status: {response.get('status', 'unknown')}")
        print(f"      Submitted At: {response.get('submitted_at', 'unknown')}")
        print(f"      Processing Time: {response.get('processing_time', 'unknown')}")
    
    # Input file information
    input_file = task_data.get('input_file', {})
    print(f"\n📁 Input File:")
    print(f"   File ID: {input_file.get('file_id', 'unknown')}")
    print(f"   File Name: {input_file.get('file_name', 'unknown')}")
    print(f"   File Size: {input_file.get('file_size', 'unknown')} bytes")
    print(f"   Storage Location: {input_file.get('storage_location', 'unknown')}")
    print(f"   Public URL: {input_file.get('public_url', 'unknown')[:80]}..." if input_file.get('public_url') else "   Public URL: None")
    
    return task_data

def check_miner_endpoint(db, miner_uid, task_id):
    """Check what the miner endpoint returns for this miner"""
    print(f"\n🔍 Checking what miner {miner_uid} sees when querying endpoint...")
    print("="*80)
    
    # Get miner API key
    users_ref = db.collection('users')
    query = users_ref.where('role', '==', 'miner').where('uid', '==', miner_uid).limit(1).stream()
    
    api_key = None
    for doc in query:
        user_data = doc.to_dict()
        api_key = user_data.get('api_key')
        break
    
    if not api_key:
        # Try to find any miner API key
        query = users_ref.where('role', '==', 'miner').limit(1).stream()
        for doc in query:
            user_data = doc.to_dict()
            api_key = user_data.get('api_key')
            break
    
    if not api_key:
        print("❌ Could not find miner API key")
        return None
    
    print(f"✅ Found API key: {api_key[:30]}...")
    
    # Test the endpoint
    BASE_URL = "http://localhost:8000"
    headers = {"X-API-Key": api_key}
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/miners/{miner_uid}/tasks",
            headers=headers,
            params={"status": "assigned"},
            timeout=10
        )
        
        print(f"\n📡 Endpoint Response:")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            tasks = response.json()
            print(f"   Tasks Returned: {len(tasks)}")
            
            # Check if our task is in the list
            task_found = False
            for task in tasks:
                if task.get('task_id') == task_id:
                    task_found = True
                    print(f"\n   ✅ Task {task_id} IS in the response!")
                    print(f"      Task Status: {task.get('status')}")
                    print(f"      Task Type: {task.get('task_type')}")
                    break
            
            if not task_found:
                print(f"\n   ❌ Task {task_id} is NOT in the response!")
                print(f"   This means the miner won't see this task!")
                
                # Show what tasks ARE returned
                if tasks:
                    print(f"\n   Tasks that ARE returned:")
                    for task in tasks:
                        print(f"      - {task.get('task_id')} (status: {task.get('status')})")
        else:
            print(f"   ❌ Error: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"   Details: {error_detail}")
            except:
                print(f"   Response: {response.text[:200]}")
    
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        import traceback
        traceback.print_exc()

def analyze_why_not_processing(db, task_data, miner_uid):
    """Analyze why the miner might not be processing the task"""
    print(f"\n🔬 Analysis: Why miner {miner_uid} might not be processing this task")
    print("="*80)
    
    issues = []
    
    # Check 1: Task status
    task_status = task_data.get('status', 'unknown')
    if task_status != 'assigned':
        issues.append(f"❌ Task status is '{task_status}', not 'assigned'. Miner only queries for 'assigned' tasks.")
    else:
        print("✅ Task status is 'assigned'")
    
    # Check 2: Miner in assigned list
    assigned_miners = task_data.get('assigned_miners', [])
    if miner_uid not in assigned_miners:
        issues.append(f"❌ Miner {miner_uid} is NOT in assigned_miners list: {assigned_miners}")
    else:
        print(f"✅ Miner {miner_uid} IS in assigned_miners list")
    
    # Check 3: Task has input file
    input_file = task_data.get('input_file', {})
    if not input_file:
        issues.append("❌ Task has no input_file data")
    else:
        file_id = input_file.get('file_id')
        public_url = input_file.get('public_url')
        if not file_id and not public_url:
            issues.append("❌ Task input_file has no file_id or public_url")
        else:
            print(f"✅ Task has input file: {file_id}")
            if public_url:
                print(f"   Public URL: {public_url[:80]}...")
    
    # Check 4: Task type is valid
    task_type = task_data.get('task_type', 'unknown')
    valid_types = ['transcription', 'tts', 'summarization', 'text_translation', 'document_translation', 'video_transcription']
    if task_type not in valid_types:
        issues.append(f"❌ Task type '{task_type}' might not be supported")
    else:
        print(f"✅ Task type '{task_type}' is valid")
    
    # Check 5: Already has responses
    miner_responses = task_data.get('miner_responses', [])
    response_from_this_miner = [r for r in miner_responses if r.get('miner_uid') == miner_uid]
    if response_from_this_miner:
        issues.append(f"⚠️ Miner {miner_uid} already has a response for this task (might be duplicate protection)")
    else:
        print(f"✅ No response from miner {miner_uid} yet")
    
    # Check 6: Task assignments status
    task_assignments = task_data.get('task_assignments', [])
    assignment_for_miner = [a for a in task_assignments if a.get('miner_uid') == miner_uid]
    if assignment_for_miner:
        assignment = assignment_for_miner[0]
        assignment_status = assignment.get('status', 'unknown')
        if assignment_status not in ['pending', 'assigned']:
            issues.append(f"⚠️ Assignment status is '{assignment_status}', not 'pending' or 'assigned'")
        else:
            print(f"✅ Assignment status is '{assignment_status}'")
    else:
        issues.append(f"⚠️ No task_assignment entry found for miner {miner_uid}")
    
    # Summary
    print(f"\n📊 Summary:")
    if issues:
        print(f"   Found {len(issues)} potential issue(s):")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("   ✅ No obvious issues found. Task should be processable.")
        print("   Possible reasons miner isn't processing:")
        print("      1. Miner is not running")
        print("      2. Miner doesn't have MINER_API_KEY set")
        print("      3. Miner can't connect to proxy server")
        print("      4. Miner is filtering out the task (duplicate protection)")
        print("      5. Miner is processing but hasn't submitted result yet")
    
    return issues

def main():
    print("="*80)
    print("🔍 Investigate Assigned Task - Why Miner Isn't Processing")
    print("="*80)
    
    db = init_firebase()
    if not db:
        return False
    
    # Get all assigned tasks
    tasks_ref = db.collection('tasks')
    query = tasks_ref.where('status', '==', 'assigned').stream()
    
    assigned_tasks = []
    for doc in query:
        task_data = doc.to_dict()
        assigned_miners = task_data.get('assigned_miners', [])
        if assigned_miners:
            task_data['task_id'] = doc.id
            assigned_tasks.append(task_data)
    
    if not assigned_tasks:
        print("\n⚠️ No tasks with status 'assigned' found")
        return True
    
    print(f"\n✅ Found {len(assigned_tasks)} assigned task(s)")
    
    # Analyze each assigned task
    for task in assigned_tasks:
        task_id = task['task_id']
        assigned_miners = task.get('assigned_miners', [])
        
        # Get detailed task information
        task_data = get_assigned_task_details(db, task_id)
        
        if task_data and assigned_miners:
            # Analyze for each assigned miner
            for miner_uid in assigned_miners:
                print(f"\n" + "="*80)
                print(f"🔍 Analyzing for Miner UID: {miner_uid}")
                print("="*80)
                
                # Analyze why not processing
                issues = analyze_why_not_processing(db, task_data, miner_uid)
                
                # Check what miner endpoint returns
                check_miner_endpoint(db, miner_uid, task_id)
    
    print("\n" + "="*80)
    print("✅ Investigation complete")
    print("="*80)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

