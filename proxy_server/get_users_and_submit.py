#!/usr/bin/env python3
"""
Get users with API keys from database and submit a transcription task
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

import firebase_admin
from firebase_admin import credentials, firestore
import requests
import time

# Configuration
BASE_URL = "http://localhost:8000"
AUDIO_FILE = "/Users/user/Documents/Jarvis/violet/LJ037-0171.wav"

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

def get_users_with_api_keys(db):
    """Get all users with API keys from database"""
    print("🔍 Fetching users with API keys from database...")
    
    try:
        users_ref = db.collection('users')
        # Query for active users with API keys
        query = users_ref.where('is_active', '==', True).stream()
        
        users = []
        for doc in query:
            user_data = doc.to_dict()
            api_key = user_data.get('api_key')
            if api_key:
                users.append({
                    'user_id': user_data.get('user_id'),
                    'email': user_data.get('email'),
                    'role': user_data.get('role', 'client'),
                    'api_key': api_key,
                    'created_at': user_data.get('created_at'),
                    'last_login': user_data.get('last_login')
                })
        
        print(f"✅ Found {len(users)} user(s) with API keys")
        return users
        
    except Exception as e:
        print(f"❌ Error fetching users: {e}")
        import traceback
        traceback.print_exc()
        return []

def display_users(users):
    """Display list of users"""
    if not users:
        print("⚠️  No users found with API keys")
        return
    
    print("\n" + "="*70)
    print("📋 Users with API Keys")
    print("="*70)
    for i, user in enumerate(users, 1):
        print(f"\n{i}. User ID: {user['user_id']}")
        print(f"   Email: {user['email']}")
        print(f"   Role: {user['role']}")
        print(f"   API Key: {user['api_key'][:30]}...")
        if user.get('created_at'):
            print(f"   Created: {user['created_at']}")
        if user.get('last_login'):
            print(f"   Last Login: {user['last_login']}")
    print("="*70)

def select_user(users):
    """Select a user (prefer client role)"""
    if not users:
        return None
    
    # Prefer client role users
    client_users = [u for u in users if u['role'] == 'client']
    if client_users:
        return client_users[0]
    
    # Fallback to any user
    return users[0]

def submit_transcription(api_key, audio_file_path):
    """Submit a transcription task using the API key"""
    print(f"\n📤 Submitting transcription task...")
    print(f"   API Key: {api_key[:30]}...")
    print(f"   Audio File: {audio_file_path}")
    
    if not os.path.exists(audio_file_path):
        print(f"❌ Audio file not found: {audio_file_path}")
        return None
    
    file_size = os.path.getsize(audio_file_path)
    print(f"   File Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    
    try:
        with open(audio_file_path, "rb") as audio_file:
            files = {
                "audio_file": (os.path.basename(audio_file_path), audio_file, "audio/wav")
            }
            data = {
                "source_language": "en",
                "priority": "normal"
            }
            headers = {
                "X-API-Key": api_key
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/transcription",
                headers=headers,
                files=files,
                data=data,
                timeout=300
            )
        
        response.raise_for_status()
        result = response.json()
        return result
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Details: {error_detail}")
            except:
                print(f"   Response: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def check_task_status(api_key, task_id):
    """Check task status"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/tasks/{task_id}",
            headers={"X-API-Key": api_key},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to get task status: {e}")
        return None

def main():
    print("="*70)
    print("🔑 Get Users from Database & Submit Transcription")
    print("="*70)
    
    # Initialize Firebase
    print("\n📦 Initializing Firebase...")
    db = init_firebase()
    if not db:
        return False
    
    # Get users with API keys
    users = get_users_with_api_keys(db)
    
    # Display users
    display_users(users)
    
    if not users:
        print("\n💡 No users found. Creating a new user...")
        # Create a new user
        from database.user_schema import UserOperations
        email = f"auto_user_{int(time.time())}@example.com"
        try:
            user_id = UserOperations.create_user(db, {
                'email': email,
                'role': 'client'
            })
            user_doc = db.collection('users').document(user_id).get()
            user_data = user_doc.to_dict()
            users = [{
                'user_id': user_data.get('user_id'),
                'email': user_data.get('email'),
                'role': user_data.get('role'),
                'api_key': user_data.get('api_key')
            }]
            print(f"✅ Created new user: {email}")
            print(f"   API Key: {user_data.get('api_key')}")
        except Exception as e:
            print(f"❌ Failed to create user: {e}")
            return False
    
    # Select a user (prefer client role)
    selected_user = select_user(users)
    if not selected_user:
        print("❌ No user selected")
        return False
    
    print(f"\n✅ Selected user:")
    print(f"   Email: {selected_user['email']}")
    print(f"   Role: {selected_user['role']}")
    print(f"   API Key: {selected_user['api_key'][:30]}...")
    
    # Check server (skip if timeout, just try to submit)
    print(f"\n🔍 Checking server at {BASE_URL}...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print(f"⚠️  Server returned status {response.status_code}")
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
        print(f"⚠️  Server health check timed out or connection failed")
        print("   Proceeding with submission anyway...")
    
    # Submit transcription
    result = submit_transcription(selected_user['api_key'], AUDIO_FILE)
    
    if result:
        task_id = result.get("task_id")
        message = result.get("message", "")
        
        print(f"\n✅ Transcription task submitted successfully!")
        print(f"   Task ID: {task_id}")
        print(f"   Message: {message}")
        
        # Get task details
        print(f"\n🔍 Fetching task details...")
        time.sleep(2)  # Wait a moment for R2 upload
        task_data = check_task_status(selected_user['api_key'], task_id)
        
        if task_data:
            status = task_data.get('status', 'unknown')
            input_file = task_data.get('input_file', {})
            storage_location = input_file.get('storage_location', 'unknown')
            public_url = input_file.get('public_url', '')
            
            print(f"   Status: {status}")
            print(f"   Storage Location: {storage_location}")
            if public_url:
                print(f"   Public URL: {public_url[:80]}...")
        
        print(f"\n📋 Task URL: {BASE_URL}/api/v1/tasks/{task_id}")
        print(f"\n💡 To check task status:")
        print(f"   curl -H 'X-API-Key: {selected_user['api_key']}' {BASE_URL}/api/v1/tasks/{task_id}")
        
        return True
    else:
        print(f"\n❌ Failed to submit transcription task")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

