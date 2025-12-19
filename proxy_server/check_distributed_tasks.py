#!/usr/bin/env python3
"""
Check distributed tasks and their assignment status
Shows which tasks are assigned to miners and whether they're being worked on
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

import firebase_admin
from firebase_admin import credentials, firestore

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

def get_all_tasks_with_assignments(db, status_filter=None):
    """Get all tasks that have been assigned to miners"""
    if status_filter:
        print(f"🔍 Fetching tasks with assignments (status: {status_filter})...")
    else:
        print("🔍 Fetching tasks with assignments...")
    
    try:
        tasks_ref = db.collection('tasks')
        
        # Get tasks with assigned_miners field
        # Filter by status if specified
        if status_filter:
            query = tasks_ref.where('status', '==', status_filter).stream()
        else:
            query = tasks_ref.stream()
        
        tasks_with_assignments = []
        for doc in query:
            task_data = doc.to_dict()
            assigned_miners = task_data.get('assigned_miners', [])
            if assigned_miners and len(assigned_miners) > 0:
                task_data['task_id'] = doc.id
                tasks_with_assignments.append(task_data)
        
        if status_filter:
            print(f"✅ Found {len(tasks_with_assignments)} task(s) with assignments (status: {status_filter})")
        else:
            print(f"✅ Found {len(tasks_with_assignments)} task(s) with assignments")
        return tasks_with_assignments
        
    except Exception as e:
        print(f"❌ Error fetching tasks: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_miner_responses_for_task(db, task_id: str) -> Dict[int, Dict]:
    """Get all miner responses for a specific task"""
    responses = {}
    
    try:
        # Method 1: Check miner_responses collection
        responses_ref = db.collection('miner_responses')
        query = responses_ref.where('task_id', '==', task_id).stream()
        
        for doc in query:
            response_data = doc.to_dict()
            miner_uid = response_data.get('miner_uid')
            if miner_uid is not None:
                responses[miner_uid] = response_data
        
        # Method 2: Check embedded responses in task document
        task_ref = db.collection('tasks').document(task_id)
        task_doc = task_ref.get()
        if task_doc.exists:
            task_data = task_doc.to_dict()
            embedded_responses = task_data.get('miner_responses', [])
            
            # If it's a list of responses
            if isinstance(embedded_responses, list):
                for response_data in embedded_responses:
                    miner_uid = response_data.get('miner_uid')
                    if miner_uid is not None:
                        # Use embedded response if we don't have one from collection
                        if miner_uid not in responses:
                            responses[miner_uid] = response_data
        
        return responses
        
    except Exception as e:
        print(f"⚠️  Error fetching miner responses: {e}")
        return {}

def get_task_assignments_status(db, task_data: Dict) -> Dict[str, Any]:
    """Get detailed status of task assignments"""
    task_id = task_data.get('task_id')
    assigned_miners = task_data.get('assigned_miners', [])
    task_assignments = task_data.get('task_assignments', [])
    task_status = task_data.get('status', 'unknown')
    
    # Get miner responses
    miner_responses = get_miner_responses_for_task(db, task_id)
    
    # Build assignment details
    assignment_details = []
    for miner_uid in assigned_miners:
        # Find assignment info
        assignment_info = None
        for assignment in task_assignments:
            if assignment.get('miner_uid') == miner_uid:
                assignment_info = assignment
                break
        
        # Get response info
        response_info = miner_responses.get(miner_uid)
        
        assignment_detail = {
            'miner_uid': miner_uid,
            'assignment_status': assignment_info.get('status', 'unknown') if assignment_info else 'unknown',
            'assigned_at': assignment_info.get('assigned_at') if assignment_info else None,
            'started_at': assignment_info.get('started_at') if assignment_info else None,
            'completed_at': assignment_info.get('completed_at') if assignment_info else None,
            'has_response': response_info is not None,
            'response_status': response_info.get('status', 'none') if response_info else 'none',
            'processing_time': response_info.get('processing_time') if response_info else None,
            'accuracy_score': response_info.get('accuracy_score') if response_info else None,
            'error_message': response_info.get('error_message') if response_info else None
        }
        
        assignment_details.append(assignment_detail)
    
    # Calculate summary
    total_assigned = len(assigned_miners)
    with_responses = sum(1 for ad in assignment_details if ad['has_response'])
    completed = sum(1 for ad in assignment_details if ad['response_status'] == 'completed')
    in_progress = sum(1 for ad in assignment_details if ad['assignment_status'] == 'in_progress')
    pending = sum(1 for ad in assignment_details if ad['assignment_status'] == 'pending')
    failed = sum(1 for ad in assignment_details if ad['response_status'] == 'failed')
    
    return {
        'task_id': task_id,
        'task_status': task_status,
        'total_assigned': total_assigned,
        'with_responses': with_responses,
        'completed': completed,
        'in_progress': in_progress,
        'pending': pending,
        'failed': failed,
        'assignments': assignment_details
    }

def format_datetime(dt) -> str:
    """Format datetime for display"""
    if dt is None:
        return "N/A"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)

def display_task_status(db, task_data: Dict):
    """Display detailed status for a task"""
    status_info = get_task_assignments_status(db, task_data)
    
    print("\n" + "="*80)
    print(f"📋 Task ID: {status_info['task_id']}")
    print("="*80)
    
    # Task info
    task_type = task_data.get('task_type', 'unknown')
    priority = task_data.get('priority', 'normal')
    created_at = task_data.get('created_at')
    distributed_at = task_data.get('distributed_at')
    
    print(f"Type: {task_type} | Priority: {priority} | Status: {status_info['task_status']}")
    print(f"Created: {format_datetime(created_at)}")
    print(f"Distributed: {format_datetime(distributed_at)}")
    
    # Summary
    print(f"\n📊 Assignment Summary:")
    print(f"   Total Assigned: {status_info['total_assigned']} miners")
    print(f"   With Responses: {status_info['with_responses']} miners")
    print(f"   Completed: {status_info['completed']} miners")
    print(f"   In Progress: {status_info['in_progress']} miners")
    print(f"   Pending: {status_info['pending']} miners")
    print(f"   Failed: {status_info['failed']} miners")
    
    # Assignment details
    print(f"\n👷 Miner Assignments:")
    for i, assignment in enumerate(status_info['assignments'], 1):
        miner_uid = assignment['miner_uid']
        assignment_status = assignment['assignment_status']
        has_response = assignment['has_response']
        response_status = assignment['response_status']
        
        # Status indicator
        if response_status == 'completed':
            status_icon = "✅"
        elif response_status == 'failed':
            status_icon = "❌"
        elif assignment_status == 'in_progress':
            status_icon = "🔄"
        elif has_response:
            status_icon = "📤"
        else:
            status_icon = "⏳"
        
        print(f"\n   {i}. Miner UID: {miner_uid} {status_icon}")
        print(f"      Assignment Status: {assignment_status}")
        print(f"      Has Response: {'Yes' if has_response else 'No'}")
        if has_response:
            print(f"      Response Status: {response_status}")
            if assignment.get('processing_time'):
                print(f"      Processing Time: {assignment['processing_time']:.2f}s")
            if assignment.get('accuracy_score'):
                print(f"      Accuracy Score: {assignment['accuracy_score']:.2f}")
        print(f"      Assigned At: {format_datetime(assignment['assigned_at'])}")
        if assignment.get('started_at'):
            print(f"      Started At: {format_datetime(assignment['started_at'])}")
        if assignment.get('completed_at'):
            print(f"      Completed At: {format_datetime(assignment['completed_at'])}")
        if assignment.get('error_message'):
            print(f"      Error: {assignment['error_message']}")

def display_summary(tasks_with_assignments: List[Dict], db):
    """Display summary of all distributed tasks"""
    print("\n" + "="*80)
    print("📊 DISTRIBUTED TASKS SUMMARY")
    print("="*80)
    
    total_tasks = len(tasks_with_assignments)
    if total_tasks == 0:
        print("⚠️  No tasks with assignments found")
        return
    
    # Count by status
    status_counts = {}
    total_miners_assigned = 0
    total_responses = 0
    
    for task in tasks_with_assignments:
        status = task.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
        
        assigned_miners = task.get('assigned_miners', [])
        total_miners_assigned += len(assigned_miners)
        
        # Count responses
        task_id = task.get('task_id')
        responses = get_miner_responses_for_task(db, task_id)
        total_responses += len(responses)
    
    print(f"\nTotal Tasks with Assignments: {total_tasks}")
    print(f"Total Miners Assigned: {total_miners_assigned}")
    print(f"Total Responses Received: {total_responses}")
    
    print(f"\n📈 Tasks by Status:")
    for status, count in sorted(status_counts.items()):
        print(f"   {status}: {count}")

def main():
    print("="*80)
    print("🔍 Check Distributed Tasks & Assignment Status")
    print("="*80)
    
    # Initialize Firebase
    print("\n📦 Initializing Firebase...")
    db = init_firebase()
    if not db:
        return False
    
    # Get tasks with assignments (only "assigned" status to reduce logging)
    tasks_with_assignments = get_all_tasks_with_assignments(db, status_filter="assigned")
    
    if not tasks_with_assignments:
        print("\n⚠️  No tasks with assignments found")
        return True
    
    # Display summary
    display_summary(tasks_with_assignments, db)
    
    # Display detailed status for each task
    print("\n" + "="*80)
    print("📋 DETAILED TASK STATUS")
    print("="*80)
    
    for task in tasks_with_assignments:
        display_task_status(db, task)
    
    print("\n" + "="*80)
    print("✅ Task status check complete")
    print("="*80)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

