#!/usr/bin/env python3
"""
Create a TTS task using the specified model and text
"""

import sys
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "https://violet-proxy-bl4w.onrender.com"
# Use provided API key
API_KEY = "tQlbLPoTF7RRsvJjgCm_4kHiIg-xqoQ6l4utqW56sY0"

# Task parameters
TEXT = "I am Tobius the great man from Iganga and Tanzania Bukoba , kammpala , masaka . We sign great work and make it work all over the world"
MODEL_ID = "tts_models/multilingual/multi-dataset/xtts_v2"
SOURCE_LANGUAGE = "en"
PRIORITY = "normal"

def get_available_voices():
    """Get list of available voices from the API"""
    print("\n" + "=" * 80)
    print("  GETTING AVAILABLE VOICES")
    print("=" * 80)
    
    url = f"{BASE_URL}/api/v1/voices"
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        if data.get("success"):
            voices = data.get("voices", [])
            print(f"\n✅ Found {len(voices)} available voice(s):\n")
            
            for i, voice in enumerate(voices, 1):
                print(f"   {i}. Voice Name: {voice.get('voice_name')}")
                print(f"      Display Name: {voice.get('display_name', 'N/A')}")
                print(f"      Language: {voice.get('language', 'N/A')}")
                print()
            
            return voices
        else:
            print(f"❌ Failed to get voices: {data.get('message', 'Unknown error')}")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error getting voices: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        return []

def create_tts_task(text, voice_name, model_id, source_language, priority):
    """Create a TTS task"""
    print("\n" + "=" * 80)
    print("  CREATING TTS TASK")
    print("=" * 80)
    
    url = f"{BASE_URL}/api/v1/tts"
    headers = {
        "X-API-Key": API_KEY
    }
    
    # Form data for TTS endpoint
    form_data = {
        "text": text,
        "voice_name": voice_name,
        "model_id": model_id,
        "source_language": source_language,
        "priority": priority
    }
    
    print(f"\n📝 Task Parameters:")
    print(f"   Text: {text[:50]}... (length: {len(text)} chars)")
    print(f"   Voice Name: {voice_name}")
    print(f"   Model ID: {model_id}")
    print(f"   Source Language: {source_language}")
    print(f"   Priority: {priority}")
    
    try:
        response = requests.post(url, headers=headers, data=form_data, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        if data.get("success"):
            task_id = data.get("task_id")
            print(f"\n✅ TTS task created successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {data.get('status', 'N/A')}")
            print(f"\n   You can check the task status at:")
            print(f"   {BASE_URL}/api/v1/tts/{task_id}/result")
            return task_id
        else:
            print(f"❌ Failed to create task: {data.get('message', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating TTS task: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text}")
        return None

def main():
    """Main function"""
    print("\n" + "=" * 80)
    print("  TTS TASK CREATION SCRIPT")
    print("=" * 80)
    
    if not API_KEY:
        print("\n❌ Error: API_KEY not found in environment variables")
        print("   Please set MINER_API_KEY, VALIDATOR_API_KEY, or API_KEY in .env file")
        return
    
    print(f"\n🔑 Using API Key: {API_KEY[:20]}...")
    print(f"🌐 Base URL: {BASE_URL}")
    
    # Step 1: Try to get available voices (optional - may fail if no permissions)
    voices = get_available_voices()
    
    # Step 2: Select a voice
    voice_name = "english_alice"  # Default voice name
    
    # Check for voice_name in command line args (overrides default)
    if len(sys.argv) > 1:
        voice_name = sys.argv[1]
        print(f"\n🎤 Using voice_name from command line: {voice_name}")
    elif voices:
        # Check if english_alice is in the available voices
        english_alice_voice = next((v for v in voices if v.get('voice_name') == 'english_alice'), None)
        if english_alice_voice:
            voice_name = "english_alice"
            print(f"\n🎤 Selected Voice: {voice_name}")
            print(f"   Display Name: {english_alice_voice.get('display_name', 'N/A')}")
            print(f"   Language: {english_alice_voice.get('language', 'N/A')}")
        else:
            # Use first available voice if english_alice not found
            selected_voice = voices[0]
            voice_name = selected_voice.get('voice_name')
            print(f"\n🎤 english_alice not found, using first available voice: {voice_name}")
            print(f"   Display Name: {selected_voice.get('display_name', 'N/A')}")
            print(f"   Language: {selected_voice.get('language', 'N/A')}")
    else:
        # Use default english_alice even if we can't list voices
        print(f"\n🎤 Using default voice: {voice_name}")
        print("   (Could not list voices - may need admin permissions)")
    
    # Step 3: Create TTS task
    task_id = create_tts_task(
        text=TEXT,
        voice_name=voice_name,  # Can be None - API will use default
        model_id=MODEL_ID,
        source_language=SOURCE_LANGUAGE,
        priority=PRIORITY
    )
    
    if task_id:
        print(f"\n✅ Task creation completed successfully!")
        print(f"   Task ID: {task_id}")
        print(f"\n   Check task status at:")
        print(f"   {BASE_URL}/api/v1/tts/{task_id}/result")
    else:
        print(f"\n❌ Task creation failed")
        print(f"\n   If the error mentions voice not found, try:")
        print(f"   1. List available voices: GET {BASE_URL}/api/v1/voices")
        print(f"   2. Or specify a voice_name as argument: python3 create_tts_task.py <voice_name>")

if __name__ == "__main__":
    main()

