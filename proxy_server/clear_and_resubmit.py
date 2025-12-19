#!/usr/bin/env python3
"""
Clear all tasks from database and resubmit a transcription task
"""

import sys
from pathlib import Path
import requests
import time

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

def clear_all_tasks(db):
    """Clear all tasks from the database"""
    print("="*80)
    print("🗑️  Clearing all tasks from database...")
    print("="*80)
    
    try:
        tasks_ref = db.collection('tasks')
        tasks = tasks_ref.stream()
        
        count = 0
        for task in tasks:
            task.reference.delete()
            count += 1
        
        print(f"✅ Deleted {count} tasks from database")
        return True
    except Exception as e:
        print(f"❌ Error clearing tasks: {e}")
        return False

def get_working_api_key(db):
    """Get a working API key from users collection"""
    print("\n" + "="*80)
    print("🔑 Getting working API key from users...")
    print("="*80)
    
    try:
        users_ref = db.collection('users')
        users = users_ref.stream()
        
        for user in users:
            user_data = user.to_dict()
            api_key = user_data.get('api_key')
            user_type = user_data.get('user_type', 'unknown')
            
            if api_key:
                print(f"✅ Found API key for user {user.id} (type: {user_type})")
                print(f"   API Key: {api_key[:20]}...")
                return api_key
        
        print("❌ No users with API keys found")
        return None
    except Exception as e:
        print(f"❌ Error getting API key: {e}")
        return None

def submit_transcription_task(api_key, audio_file_path, model_id):
    """Submit a transcription task"""
    print("\n" + "="*80)
    print("📤 Submitting transcription task...")
    print("="*80)
    print(f"   Audio file: {audio_file_path}")
    print(f"   Model ID: {model_id}")
    print(f"   API Key: {api_key[:20]}...")
    
    base_url = "http://localhost:8000"
    
    try:
        with open(audio_file_path, 'rb') as f:
            files = {
                'audio_file': (Path(audio_file_path).name, f, 'audio/wav')
            }
            data = {
                'source_language': 'en',
                'priority': 'normal',
                'model_id': model_id
            }
            headers = {
                'X-API-Key': api_key
            }
            
            print(f"\n📡 Sending request to {base_url}/api/v1/transcription...")
            response = requests.post(
                f"{base_url}/api/v1/transcription",
                files=files,
                data=data,
                headers=headers,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Task submitted successfully!")
                print(f"   Task ID: {result.get('task_id')}")
                return result.get('task_id')
            else:
                print(f"❌ Error submitting task: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
    except FileNotFoundError:
        print(f"❌ Audio file not found: {audio_file_path}")
        return None
    except Exception as e:
        print(f"❌ Error submitting task: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    # Initialize Firebase
    db = init_firebase()
    if not db:
        return False
    
    # Clear all tasks
    if not clear_all_tasks(db):
        return False
    
    # Get working API key
    api_key = get_working_api_key(db)
    if not api_key:
        return False
    
    # Audio file path
    audio_file = Path(__file__).parent.parent / "LJ037-0171.wav"
    if not audio_file.exists():
        print(f"\n❌ Audio file not found: {audio_file}")
        print("   Please provide the path to an audio file")
        return False
    
    # Submit transcription task
    model_id = "openai/whisper-tiny"
    task_id = submit_transcription_task(api_key, str(audio_file), model_id)
    
    if task_id:
        print("\n" + "="*80)
        print("✅ Success!")
        print("="*80)
        print(f"   Task ID: {task_id}")
        print(f"   Model ID: {model_id}")
        print(f"   Check task status: http://localhost:8000/api/v1/tasks/{task_id}")
        return True
    else:
        print("\n❌ Failed to submit task")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

