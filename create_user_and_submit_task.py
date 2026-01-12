#!/usr/bin/env python3
"""
Script to:
1. Register a new user via API
2. Generate an API key for that user
3. Use the API key to submit a transcription task
"""

import sys
import os
import asyncio
from datetime import datetime

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import httpx
import json

# Configuration
PROXY_SERVER_URL = "https://violet-proxy-bl4w.onrender.com"
AUDIO_FILE_PATH = "/Users/user/Documents/Jarvis/violet/tests/chatterbox_test_output.wav"
MODEL_ID = "openai/whisper-tiny"
SOURCE_LANGUAGE = "en"

# Generate unique email for this test
import random
import string
random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
TEST_EMAIL = f"test_user_{random_suffix}@example.com"

def print_section(title: str):
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")

async def register_user(email: str, role: str = "client") -> dict:
    """Register a new user"""
    print_section("Step 1: Registering User")
    print(f"   Email: {email}")
    print(f"   Role: {role}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{PROXY_SERVER_URL}/api/v1/auth/register",
                json={
                    "email": email,
                    "role": role
                }
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"✅ User registered successfully!")
                print(f"   Response: {json.dumps(result, indent=2)}")
                return result
            else:
                print(f"❌ Registration failed with status {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Error registering user: {e}")
        import traceback
        traceback.print_exc()
        return None

async def generate_api_key(email: str, target_role: str = "client") -> dict:
    """Generate an API key for the user"""
    print_section("Step 2: Generating API Key")
    print(f"   Email: {email}")
    print(f"   Target Role: {target_role}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # For client role, we don't need hotkey/coldkey/uid/network
            request_body = {
                "email": email,
                "target_role": target_role
            }
            
            response = await client.post(
                f"{PROXY_SERVER_URL}/api/v1/auth/generate-api-key",
                json=request_body
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"✅ API key generated successfully!")
                print(f"   API Key: {result.get('api_key', 'N/A')}")
                print(f"   Role: {result.get('role', 'N/A')}")
                print(f"   Message: {result.get('message', 'N/A')}")
                return result
            else:
                print(f"❌ API key generation failed with status {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Error generating API key: {e}")
        import traceback
        traceback.print_exc()
        return None

async def submit_transcription_task(api_key: str, file_path: str, model_id: str, source_language: str) -> dict:
    """Submit a transcription task using the API key"""
    print_section("Step 3: Submitting Transcription Task")
    print(f"   File: {file_path}")
    print(f"   Model: {model_id}")
    print(f"   Language: {source_language}")
    
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return None
    
    file_size = os.path.getsize(file_path)
    print(f"   File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {
                "X-API-Key": api_key
            }
            
            # Read file
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Prepare multipart form data
            files = {
                'audio_file': (os.path.basename(file_path), file_data, 'audio/wav')
            }
            data = {
                'model_id': model_id,
                'source_language': source_language,
                'priority': 'normal'
            }
            
            endpoint = f"{PROXY_SERVER_URL}/api/v1/transcription"
            print(f"   Endpoint: {endpoint}")
            print(f"   Sending request...")
            
            response = await client.post(
                endpoint,
                headers=headers,
                files=files,
                data=data
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                task_id = result.get("task_id") or result.get("id")
                file_id = result.get("file_id") or result.get("input_file_id")
                
                print(f"✅ Transcription task created successfully!")
                print(f"   Task ID: {task_id}")
                if file_id:
                    print(f"   File ID: {file_id}")
                print(f"   Full Response: {json.dumps(result, indent=2)}")
                
                return {
                    "task_id": task_id,
                    "file_id": file_id,
                    "file_size": file_size,
                    "status": result.get("status", "created"),
                    "result": result
                }
            else:
                print(f"❌ Task creation failed with status {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
    except httpx.TimeoutException:
        print(f"❌ Request timeout - file may be too large")
        return None
    except Exception as e:
        print(f"❌ Error creating task: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """Main function"""
    print_section("Create User and Submit Transcription Task")
    print(f"Proxy Server: {PROXY_SERVER_URL}")
    print(f"Test Email: {TEST_EMAIL}")
    print(f"Audio File: {AUDIO_FILE_PATH}")
    print(f"Model: {MODEL_ID}")
    print(f"Language: {SOURCE_LANGUAGE}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Step 1: Register user
    register_result = await register_user(TEST_EMAIL, role="client")
    if not register_result:
        print("\n❌ Failed to register user. Cannot continue.")
        return
    
    # Step 2: Generate API key
    api_key_result = await generate_api_key(TEST_EMAIL, target_role="client")
    if not api_key_result:
        print("\n❌ Failed to generate API key. Cannot continue.")
        return
    
    api_key = api_key_result.get("api_key")
    if not api_key:
        print("\n❌ No API key in response. Cannot continue.")
        return
    
    # Step 3: Submit transcription task
    task_result = await submit_transcription_task(
        api_key=api_key,
        file_path=AUDIO_FILE_PATH,
        model_id=MODEL_ID,
        source_language=SOURCE_LANGUAGE
    )
    
    # Summary
    print_section("✅ SUMMARY")
    print(f"User Email: {TEST_EMAIL}")
    print(f"API Key: {api_key[:20]}... (truncated)")
    if task_result:
        print(f"Task ID: {task_result.get('task_id')}")
        print(f"File ID: {task_result.get('file_id')}")
        print(f"Status: {task_result.get('status')}")
    else:
        print("Task: Failed to create")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())

