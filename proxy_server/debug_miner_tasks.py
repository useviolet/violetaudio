#!/usr/bin/env python3
"""
Debug script to check what tasks the miner endpoint returns
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import firebase_admin
from firebase_admin import credentials, firestore
from database.enhanced_schema import DatabaseOperations

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

def main():
    print("="*80)
    print("🔍 Debug: What tasks does miner UID 6 get?")
    print("="*80)
    
    db = init_firebase()
    if not db:
        return False
    
    miner_uid = 6
    
    # Test different statuses
    for status in ["assigned", "pending", "processing"]:
        print(f"\n📋 Testing status: '{status}'")
        print("-" * 80)
        
        try:
            tasks = DatabaseOperations.get_miner_tasks(db, miner_uid, status)
            print(f"✅ Found {len(tasks)} tasks with status '{status}'")
            
            for i, task in enumerate(tasks, 1):
                task_id = task.get('task_id', 'unknown')
                task_type = task.get('task_type', 'unknown')
                task_status = task.get('status', 'unknown')
                assigned_miners = task.get('assigned_miners', [])
                
                print(f"\n   {i}. Task ID: {task_id}")
                print(f"      Type: {task_type}")
                print(f"      Status: {task_status}")
                print(f"      Assigned Miners: {assigned_miners}")
                
                # Check if miner is in assigned list
                if miner_uid in assigned_miners:
                    print(f"      ✅ Miner {miner_uid} IS in assigned_miners list")
                else:
                    print(f"      ❌ Miner {miner_uid} is NOT in assigned_miners list")
        
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Also check what the actual task statuses are
    print(f"\n" + "="*80)
    print("📊 Actual task statuses in database:")
    print("="*80)
    
    tasks_ref = db.collection('tasks')
    all_tasks = tasks_ref.stream()
    
    tasks_by_status = {}
    for doc in all_tasks:
        task_data = doc.to_dict()
        status = task_data.get('status', 'unknown')
        assigned_miners = task_data.get('assigned_miners', [])
        
        if miner_uid in assigned_miners:
            if status not in tasks_by_status:
                tasks_by_status[status] = []
            tasks_by_status[status].append({
                'task_id': doc.id,
                'task_type': task_data.get('task_type', 'unknown'),
                'status': status
            })
    
    for status, tasks in tasks_by_status.items():
        print(f"\n{status}: {len(tasks)} tasks")
        for task in tasks:
            print(f"   - {task['task_id']} ({task['task_type']})")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

