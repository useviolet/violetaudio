#!/usr/bin/env python3
"""
Fix old task that has database storage but no file_id
Either migrate to R2 or mark as failed
"""

import sys
from pathlib import Path

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

def main():
    print("="*80)
    print("🔧 Fix Old Task - Add Missing file_id")
    print("="*80)
    
    db = init_firebase()
    if not db:
        return False
    
    task_id = "927c3094-509a-45f5-867c-1e43b896099e"
    
    # Get task
    task_ref = db.collection('tasks').document(task_id)
    task_doc = task_ref.get()
    
    if not task_doc.exists:
        print(f"❌ Task {task_id} not found")
        return False
    
    task_data = task_doc.to_dict()
    input_file = task_data.get('input_file', {})
    
    print(f"\n📋 Current task input_file:")
    print(f"   File Name: {input_file.get('file_name')}")
    print(f"   File Size: {input_file.get('file_size')}")
    print(f"   Storage Location: {input_file.get('storage_location')}")
    print(f"   File ID: {input_file.get('file_id', 'MISSING')}")
    
    # Check if file exists in files collection by name
    files_ref = db.collection('files')
    query = files_ref.where('original_filename', '==', input_file.get('file_name')).limit(1).stream()
    
    file_found = None
    for doc in query:
        file_found = doc.to_dict()
        file_found['file_id'] = doc.id
        break
    
    if file_found:
        print(f"\n✅ Found file in files collection:")
        print(f"   File ID: {file_found['file_id']}")
        print(f"   Storage Location: {file_found.get('storage_location', 'unknown')}")
        
        # Update task with file_id
        input_file['file_id'] = file_found['file_id']
        if 'storage_location' not in input_file or input_file['storage_location'] == 'database':
            # Update storage location if it's in R2
            if file_found.get('storage_location') == 'r2':
                input_file['storage_location'] = 'r2'
                input_file['public_url'] = file_found.get('public_url')
                print(f"   ✅ Updated to R2 storage")
        
        task_ref.update({
            'input_file': input_file,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        print(f"\n✅ Task updated with file_id: {file_found['file_id']}")
        return True
    else:
        print(f"\n⚠️  File not found in files collection")
        print(f"   This task may need to be recreated or marked as failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

