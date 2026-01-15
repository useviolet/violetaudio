#!/usr/bin/env python3
"""
Script to create a transcription task in the database via proxy server API.
Uploads the audio file first, then creates the task.
"""

import os
import sys
import httpx
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
PROXY_SERVER_URL = "https://violet-proxy-bl4w.onrender.com"
AUDIO_FILE_PATH = "/Users/user/Documents/Jarvis/violet/tests/chatterbox_test_output.wav"
MODEL_ID = "openai/whisper-tiny"
SOURCE_LANGUAGE = "en"

# Get API key from environment
API_KEY = os.getenv('VALIDATOR_API_KEY') or os.getenv('MINER_API_KEY')

if not API_KEY:
    print("❌ Error: API key not found!")
    print("   Please set VALIDATOR_API_KEY or MINER_API_KEY in your .env file")
    sys.exit(1)

def get_headers():
    """Get authentication headers"""
    return {
        "X-API-Key": API_KEY
    }

async def create_transcription_task_with_file(file_path: str, model_id: str, source_language: str = "en") -> dict:
    """Create transcription task directly with file upload using /api/v1/transcription endpoint"""
    print(f"\n📤 Creating transcription task with file: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return None
    
    file_size = os.path.getsize(file_path)
    print(f"   File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    print(f"   Model: {model_id}")
    print(f"   Language: {source_language}")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = get_headers()
            
            # Read file
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Prepare multipart form data for transcription endpoint
            files = {
                'file': (os.path.basename(file_path), file_data, 'audio/wav')
            }
            data = {
                'model_id': model_id,
                'source_language': source_language,
                'priority': 'normal',
                'required_miner_count': '3',
                'min_miner_count': '1',
                'max_miner_count': '5'
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
    """Main function to upload file and create task"""
    print("=" * 80)
    print("🎯 Creating Transcription Task")
    print("=" * 80)
    print(f"Proxy Server: {PROXY_SERVER_URL}")
    print(f"Audio File: {AUDIO_FILE_PATH}")
    print(f"Model: {MODEL_ID}")
    print(f"Language: {SOURCE_LANGUAGE}")
    print("=" * 80)
    
    # Create transcription task directly with file
    task_info = await create_transcription_task_with_file(
        AUDIO_FILE_PATH,
        MODEL_ID,
        SOURCE_LANGUAGE
    )
    
    if not task_info:
        print("\n❌ Failed to create transcription task.")
        return
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ SUCCESS!")
    print("=" * 80)
    print(f"Task ID: {task_info['task_id']}")
    if task_info.get('file_id'):
        print(f"File ID: {task_info['file_id']}")
    print(f"Model: {MODEL_ID}")
    print(f"Language: {SOURCE_LANGUAGE}")
    print(f"Status: {task_info.get('status', 'created')}")
    print(f"File Size: {task_info['file_size']:,} bytes")
    print("\nYou can check the task status using:")
    print(f"  GET {PROXY_SERVER_URL}/api/v1/tasks/{task_info['task_id']}")
    print("=" * 80)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

