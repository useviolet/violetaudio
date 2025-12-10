#!/usr/bin/env python3
"""
Script to check database for tasks and miners
"""

import os
import sys
from datetime import datetime

# Add proxy_server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'proxy_server'))

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("❌ Firebase Admin SDK not installed. Install with: pip install firebase-admin")
    sys.exit(1)

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        # Check if already initialized
        if firebase_admin._apps:
            return firestore.client()
        
        # Try to find credentials file
        cred_paths = [
            "proxy_server/db/violet.json",
            "db/violet.json",
            "violet.json"
        ]
        
        cred_path = None
        for path in cred_paths:
            if os.path.exists(path):
                cred_path = path
                break
        
        if not cred_path:
            print("⚠️  Firebase credentials file not found. Trying to use default credentials...")
            # Try to use default credentials (if running on GCP or with GOOGLE_APPLICATION_CREDENTIALS env var)
            try:
                cred = credentials.ApplicationDefault()
            except:
                print("❌ Could not initialize Firebase. Please provide credentials file.")
                return None
        else:
            print(f"✅ Using credentials from: {cred_path}")
            cred = credentials.Certificate(cred_path)
        
        # Initialize Firebase
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase initialized successfully")
        return db
        
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        return None

def get_tasks(db):
    """Get all tasks from database"""
    try:
        tasks_ref = db.collection('tasks')
        tasks = tasks_ref.stream()
        
        task_list = []
        for task in tasks:
            task_data = task.to_dict()
            task_data['id'] = task.id
            task_list.append(task_data)
        
        return task_list
    except Exception as e:
        print(f"❌ Error getting tasks: {e}")
        return []

def get_miners(db):
    """Get all miners from database"""
    try:
        miners_ref = db.collection('miners')
        miners = miners_ref.stream()
        
        miner_list = []
        for miner in miners:
            miner_data = miner.to_dict()
            miner_data['id'] = miner.id
            miner_list.append(miner_data)
        
        return miner_list
    except Exception as e:
        print(f"❌ Error getting miners: {e}")
        return []

def format_datetime(dt):
    """Format datetime for display"""
    if dt is None:
        return "N/A"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)

def main():
    print("=" * 80)
    print("Database Check - Tasks and Miners")
    print("=" * 80)
    print()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("❌ Could not connect to database")
        return
    
    print()
    print("=" * 80)
    print("TASKS")
    print("=" * 80)
    
    tasks = get_tasks(db)
    print(f"\n📋 Total Tasks: {len(tasks)}")
    
    if tasks:
        print("\nTask Details:")
        print("-" * 80)
        for i, task in enumerate(tasks, 1):
            print(f"\n{i}. Task ID: {task.get('id', 'N/A')}")
            print(f"   Task Type: {task.get('task_type', 'N/A')}")
            print(f"   Status: {task.get('status', 'N/A')}")
            print(f"   Priority: {task.get('priority', 'N/A')}")
            print(f"   Created At: {format_datetime(task.get('created_at'))}")
            print(f"   Updated At: {format_datetime(task.get('updated_at'))}")
            
            # Show input data summary
            if 'input_data' in task:
                input_data = task['input_data']
                if isinstance(input_data, str):
                    print(f"   Input Data: {len(input_data)} characters")
                elif isinstance(input_data, dict):
                    print(f"   Input Data: {len(str(input_data))} characters (dict)")
                else:
                    print(f"   Input Data: {type(input_data).__name__}")
            
            if 'input_file' in task:
                print(f"   Input File: {task['input_file'].get('file_name', 'N/A')}")
            
            # Show miner responses
            if 'miner_responses' in task:
                responses = task.get('miner_responses', [])
                print(f"   Miner Responses: {len(responses)}")
                for resp in responses[:3]:  # Show first 3
                    print(f"     - Miner {resp.get('miner_uid', 'N/A')}: {resp.get('status', 'N/A')}")
            
            # Show assigned miners
            if 'assigned_miners' in task:
                assigned = task.get('assigned_miners', [])
                print(f"   Assigned Miners: {len(assigned)}")
                for miner_uid in assigned[:5]:  # Show first 5
                    print(f"     - Miner UID: {miner_uid}")
    else:
        print("\n⚠️  No tasks found in database")
    
    print()
    print("=" * 80)
    print("MINERS")
    print("=" * 80)
    
    miners = get_miners(db)
    print(f"\n⛏️  Total Miners: {len(miners)}")
    
    if miners:
        print("\nMiner Details:")
        print("-" * 80)
        for i, miner in enumerate(miners, 1):
            print(f"\n{i}. Miner ID: {miner.get('id', 'N/A')}")
            print(f"   UID: {miner.get('uid', 'N/A')}")
            print(f"   Hotkey: {miner.get('hotkey', 'N/A')}")
            print(f"   Is Serving: {miner.get('is_serving', False)}")
            print(f"   Stake: {miner.get('stake', 0)}")
            print(f"   Last Seen: {format_datetime(miner.get('last_seen'))}")
            print(f"   Updated At: {format_datetime(miner.get('updated_at'))}")
            
            # Show consensus data if available
            if 'consensus_status' in miner:
                consensus = miner.get('consensus_status', {})
                print(f"   Consensus Status: {consensus.get('status', 'N/A')}")
                print(f"   Consensus Confidence: {consensus.get('confidence', 0)}")
            
            # Show IP/Port info
            if 'ip' in miner:
                print(f"   IP: {miner.get('ip', 'N/A')}")
            if 'port' in miner:
                print(f"   Port: {miner.get('port', 'N/A')}")
            if 'external_ip' in miner:
                print(f"   External IP: {miner.get('external_ip', 'N/A')}")
            if 'external_port' in miner:
                print(f"   External Port: {miner.get('external_port', 'N/A')}")
    else:
        print("\n⚠️  No miners found in database")
    
    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"✅ Tasks: {len(tasks)}")
    print(f"✅ Miners: {len(miners)}")
    print()

if __name__ == "__main__":
    main()

