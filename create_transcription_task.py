#!/usr/bin/env python3
"""
Create transcription tasks using different Whisper models
"""

import sys
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "https://violet-proxy-bl4w.onrender.com"
API_KEY = "tQlbLPoTF7RRsvJjgCm_4kHiIg-xqoQ6l4utqW56sY0"

# Task parameters
AUDIO_FILE_PATH = "/Users/user/Documents/Jarvis/violet/LJ037-0171.wav"
SOURCE_LANGUAGE = "en"
PRIORITY = "normal"

# Model IDs to test
MODEL_IDS = [
    "openai/whisper-large-v3",
    "openai/whisper-medium",
    "openai/whisper-small",
    "openai/whisper-base",
    "openai/whisper-tiny"
]

def create_transcription_task(audio_file_path, model_id, source_language, priority):
    """Create a transcription task"""
    print("\n" + "=" * 80)
    print(f"  CREATING TRANSCRIPTION TASK - {model_id}")
    print("=" * 80)
    
    url = f"{BASE_URL}/api/v1/transcription"
    headers = {
        "X-API-Key": API_KEY
    }
    
    # Check if audio file exists
    if not os.path.exists(audio_file_path):
        print(f"❌ Audio file not found: {audio_file_path}")
        return None
    
    # Prepare form data with file upload
    with open(audio_file_path, 'rb') as audio_file:
        files = {
            'audio_file': (os.path.basename(audio_file_path), audio_file, 'audio/wav')
        }
        form_data = {
            'source_language': source_language,
            'model_id': model_id,
            'priority': priority
        }
        
        print(f"\n📝 Task Parameters:")
        print(f"   Audio File: {os.path.basename(audio_file_path)}")
        print(f"   File Size: {os.path.getsize(audio_file_path):,} bytes")
        print(f"   Model ID: {model_id}")
        print(f"   Source Language: {source_language}")
        print(f"   Priority: {priority}")
        
        try:
            response = requests.post(url, headers=headers, files=files, data=form_data, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success"):
                task_id = data.get("task_id")
                print(f"\n✅ Transcription task created successfully!")
                print(f"   Task ID: {task_id}")
                print(f"   Status: {data.get('status', 'N/A')}")
                print(f"\n   You can check the task status at:")
                print(f"   {BASE_URL}/api/v1/transcription/{task_id}/result")
                return task_id
            else:
                print(f"❌ Failed to create task: {data.get('message', 'Unknown error')}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error creating transcription task: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status Code: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return None

def main():
    """Main function"""
    print("\n" + "=" * 80)
    print("  TRANSCRIPTION TASK CREATION SCRIPT")
    print("=" * 80)
    
    if not API_KEY:
        print("\n❌ Error: API_KEY not found")
        return
    
    print(f"\n🔑 Using API Key: {API_KEY[:20]}...")
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"📁 Audio File: {AUDIO_FILE_PATH}")
    
    # Check if audio file exists
    if not os.path.exists(AUDIO_FILE_PATH):
        print(f"\n❌ Error: Audio file not found: {AUDIO_FILE_PATH}")
        return
    
    print(f"\n✅ Audio file found: {os.path.getsize(AUDIO_FILE_PATH):,} bytes")
    
    # Create tasks for each model
    task_ids = []
    for model_id in MODEL_IDS:
        task_id = create_transcription_task(
            audio_file_path=AUDIO_FILE_PATH,
            model_id=model_id,
            source_language=SOURCE_LANGUAGE,
            priority=PRIORITY
        )
        if task_id:
            task_ids.append((model_id, task_id))
    
    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    
    if task_ids:
        print(f"\n✅ Successfully created {len(task_ids)} transcription task(s):\n")
        for model_id, task_id in task_ids:
            print(f"   {model_id}:")
            print(f"      Task ID: {task_id}")
            print(f"      Status URL: {BASE_URL}/api/v1/transcription/{task_id}/result")
            print()
    else:
        print("\n❌ No tasks were created successfully")

if __name__ == "__main__":
    main()
