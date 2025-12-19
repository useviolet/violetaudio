"""
Submit transcription task using provided API key
Supports both localhost and Render deployment
"""

import requests
import os
import sys
from pathlib import Path

# Try Render URL first, fallback to localhost
BASE_URL = os.getenv("PROXY_URL", "https://violet-proxy-bl4w.onrender.com")
# Uncomment below to use localhost instead:
# BASE_URL = "http://localhost:8000"

# API Key - if invalid, the script will attempt to register a new user
API_KEY = "ed801923-2f1c-4184-a068-78f50932b358"
AUDIO_FILE = "/Users/user/Documents/Jarvis/violet/LJ037-0171.wav"

def register_user(email, base_url):
    """Register a new user and get API key"""
    try:
        response = requests.post(
            f"{base_url}/api/v1/auth/register",
            json={"email": email, "role": "client"},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        return result.get('api_key')
    except Exception as e:
        print(f"❌ Failed to register user: {e}")
        return None

def check_server(base_url):
    """Check if server is accessible"""
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            return True
        return False
    except:
        return False

def verify_api_key(api_key, base_url):
    """Verify API key is valid"""
    headers = {"X-API-Key": api_key}
    try:
        response = requests.get(
            f"{base_url}/api/v1/auth/verify-api-key",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            return True, response.json()
        return False, None
    except Exception as e:
        return False, str(e)

def submit_transcription(api_key, audio_file_path, base_url):
    """Submit a transcription task"""
    headers = {"X-API-Key": api_key}
    
    print(f"📤 Submitting transcription task...")
    print(f"   Base URL: {base_url}")
    print(f"   Audio file: {audio_file_path}")
    print(f"   API Key: {api_key[:20]}...")
    
    if not os.path.exists(audio_file_path):
        print(f"❌ Audio file not found: {audio_file_path}")
        return None
    
    file_size = os.path.getsize(audio_file_path)
    print(f"   File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    
    try:
        with open(audio_file_path, 'rb') as f:
            files = {'audio_file': (os.path.basename(audio_file_path), f, 'audio/wav')}
            data = {
                'source_language': 'en',
                'priority': 'normal'
            }
            response = requests.post(
                f"{base_url}/api/v1/transcription",
                headers=headers,
                files=files,
                data=data,
                timeout=300  # 5 minutes timeout for large files
            )
        
        response.raise_for_status()
        result = response.json()
        return result
        
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out. The file might be too large or server is slow.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Error details: {error_detail}")
            except:
                print(f"   Response text: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Error submitting transcription: {e}")
        return None

def get_task_status(api_key, task_id, base_url):
    """Get task status"""
    headers = {"X-API-Key": api_key}
    try:
        response = requests.get(
            f"{base_url}/api/v1/tasks/{task_id}",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️  Failed to get task status: {e}")
        return None

def main():
    print("="*70)
    print("🎤 Submit Transcription Task")
    print("="*70)
    
    # Check if we should try localhost first
    if "--local" in sys.argv or "-l" in sys.argv:
        global BASE_URL
        BASE_URL = "http://localhost:8000"
        print(f"📍 Using localhost mode")
    
    # Check server connectivity
    print(f"\n🔍 Checking server connectivity...")
    if check_server(BASE_URL):
        print(f"✅ Server is accessible at {BASE_URL}")
    else:
        print(f"⚠️  Server health check failed at {BASE_URL}")
        print(f"   Attempting to submit anyway...")
    
    # Verify API key
    print(f"\n🔑 Verifying API key...")
    api_key_to_use = API_KEY
    is_valid, key_info = verify_api_key(API_KEY, BASE_URL)
    if is_valid:
        print(f"✅ API key is valid")
        if key_info:
            email = key_info.get('email', 'unknown')
            role = key_info.get('role', 'unknown')
            print(f"   Email: {email}")
            print(f"   Role: {role}")
    else:
        print(f"⚠️  API key verification failed")
        if key_info:
            print(f"   Error: {key_info}")
        print(f"\n💡 Attempting to register a new user...")
        import time
        new_email = f"user_{int(time.time())}@example.com"
        new_api_key = register_user(new_email, BASE_URL)
        if new_api_key:
            print(f"✅ Registered new user: {new_email}")
            print(f"   New API Key: {new_api_key}")
            api_key_to_use = new_api_key
        else:
            print(f"❌ Failed to register new user. Using provided API key anyway...")
    
    # Submit transcription
    result = submit_transcription(api_key_to_use, AUDIO_FILE, BASE_URL)
    
    if result:
        task_id = result.get("task_id")
        message = result.get("message", "")
        
        print(f"\n✅ Transcription task submitted successfully!")
        print(f"   Task ID: {task_id}")
        print(f"   Message: {message}")
        
        # Get task details
        print(f"\n🔍 Fetching task details...")
        task_data = get_task_status(api_key_to_use, task_id, BASE_URL)
        
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
        print(f"   curl -H 'X-API-Key: {api_key_to_use}' {BASE_URL}/api/v1/tasks/{task_id}")
        
        return True
    else:
        print(f"\n❌ Failed to submit transcription task")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

