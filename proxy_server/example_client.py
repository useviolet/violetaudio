#!/usr/bin/env python3
"""
Simple example client for submitting transcription tasks
Usage: python example_client.py [audio_file_path]
"""

import requests
import sys
import time
import os
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"  # Change to production URL if needed
# BASE_URL = "https://violet-proxy-bl4w.onrender.com"  # Production

def register_user(email: str) -> str:
    """Register a new user and get API key"""
    print(f"📝 Registering user: {email}...")
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={"email": email, "role": "client"},
        timeout=30
    )
    response.raise_for_status()
    data = response.json()
    api_key = data["api_key"]
    print(f"✅ Registered! API Key: {api_key[:20]}...")
    return api_key

def submit_transcription(api_key: str, audio_file_path: str) -> str:
    """Submit a transcription task"""
    print(f"\n📤 Submitting transcription task...")
    print(f"   File: {audio_file_path}")
    
    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
    
    file_size = os.path.getsize(audio_file_path)
    print(f"   Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    
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
    task_id = result["task_id"]
    print(f"✅ Task submitted!")
    print(f"   Task ID: {task_id}")
    return task_id

def check_task_status(api_key: str, task_id: str) -> dict:
    """Check task status"""
    response = requests.get(
        f"{BASE_URL}/api/v1/tasks/{task_id}",
        headers={"X-API-Key": api_key},
        timeout=30
    )
    response.raise_for_status()
    return response.json()

def get_result(api_key: str, task_id: str) -> dict:
    """Get transcription result"""
    response = requests.get(
        f"{BASE_URL}/api/v1/transcription/{task_id}/result",
        headers={"X-API-Key": api_key},
        timeout=30
    )
    response.raise_for_status()
    return response.json()

def wait_for_completion(api_key: str, task_id: str, max_wait: int = 300) -> bool:
    """Wait for task to complete"""
    print(f"\n⏳ Waiting for transcription to complete...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        task_data = check_task_status(api_key, task_id)
        status = task_data["status"]
        
        print(f"   Status: {status}", end="\r")
        
        if status == "completed":
            print(f"\n✅ Transcription completed!")
            return True
        elif status == "failed":
            print(f"\n❌ Transcription failed")
            return False
        elif status == "cancelled":
            print(f"\n⚠️  Transcription cancelled")
            return False
        
        time.sleep(5)
    
    print(f"\n⏱️  Timeout after {max_wait} seconds")
    return False

def main():
    print("="*70)
    print("🎤 Violet Transcription API - Example Client")
    print("="*70)
    
    # Get audio file path
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
    else:
        # Default test file
        audio_file = "/Users/user/Documents/Jarvis/violet/LJ037-0171.wav"
        if not os.path.exists(audio_file):
            print("❌ Please provide an audio file path as argument")
            print("   Usage: python example_client.py [audio_file_path]")
            sys.exit(1)
    
    # Check server
    print(f"\n🔍 Checking server at {BASE_URL}...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print(f"⚠️  Server returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print("   Make sure the server is running")
        sys.exit(1)
    
    # Register user (or use existing API key)
    import time
    email = f"client_{int(time.time())}@example.com"
    api_key = register_user(email)
    
    # Submit transcription
    try:
        task_id = submit_transcription(api_key, audio_file)
        
        # Wait for completion
        if wait_for_completion(api_key, task_id):
            # Get result
            print(f"\n📝 Getting transcription result...")
            result = get_result(api_key, task_id)
            
            print("\n" + "="*70)
            print("📄 TRANSCRIPTION RESULT")
            print("="*70)
            print(result.get("transcript", "No transcript available"))
            print("="*70)
            
            if "confidence" in result:
                print(f"\nConfidence: {result['confidence']:.2%}")
            if "language" in result:
                print(f"Language: {result['language']}")
            if "processing_time" in result:
                print(f"Processing Time: {result['processing_time']:.2f}s")
        else:
            print("\n⚠️  Task did not complete. Check status manually:")
            print(f"   curl -H 'X-API-Key: {api_key}' {BASE_URL}/api/v1/tasks/{task_id}")
    
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Details: {error_detail}")
            except:
                print(f"   Response: {e.response.text[:500]}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

