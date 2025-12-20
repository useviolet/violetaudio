"""
Test script for voice management endpoints and TTS task creation
"""

import requests
import os
import sys
from pathlib import Path

# Try localhost first, fallback to Render URL
BASE_URL = os.getenv("PROXY_URL", "http://localhost:8000")
# Uncomment below to use Render instead:
# BASE_URL = "https://violet-proxy-bl4w.onrender.com"

# API Key - update this with a valid API key
API_KEY = os.getenv("API_KEY", "ed801923-2f1c-4184-a068-78f50932b358")

# Test voice details
VOICE_NAME = "test_voice_alice"
DISPLAY_NAME = "Test Voice Alice"
LANGUAGE = "en"

# Sample audio file path (you can use any WAV file)
# For testing, you can use a sample audio file or create one
AUDIO_FILE_PATH = os.getenv("AUDIO_FILE", "/Users/user/Documents/Jarvis/violet/LJ037-0171.wav")

def check_server(base_url):
    """Check if server is accessible"""
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        return response.status_code == 200
    except:
        return False

def list_voices(base_url, api_key):
    """List all voices"""
    print("\n" + "="*80)
    print("📋 LISTING VOICES")
    print("="*80)
    try:
        response = requests.get(
            f"{base_url}/api/v1/voices",
            headers={"X-API-Key": api_key},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        print(f"✅ Successfully listed {result.get('count', 0)} voices")
        for voice in result.get('voices', []):
            print(f"   - {voice.get('voice_name')}: {voice.get('display_name')} ({voice.get('language')})")
        return result
    except Exception as e:
        print(f"❌ Failed to list voices: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        return None

def add_voice(base_url, api_key, voice_name, display_name, language, audio_file_path):
    """Add a new voice"""
    print("\n" + "="*80)
    print(f"➕ ADDING VOICE: {voice_name}")
    print("="*80)
    
    if not os.path.exists(audio_file_path):
        print(f"❌ Audio file not found: {audio_file_path}")
        print("   Creating a dummy audio file for testing...")
        # Create a minimal WAV file for testing
        import wave
        import struct
        sample_rate = 44100
        duration = 1  # 1 second
        frequency = 440  # A4 note
        
        with wave.open(audio_file_path, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            
            for i in range(int(sample_rate * duration)):
                value = int(32767 * 0.3 * (i / sample_rate * 2 * 3.14159 * frequency))
                wav_file.writeframes(struct.pack('<h', value))
        
        print(f"   ✅ Created dummy audio file: {audio_file_path}")
    
    try:
        with open(audio_file_path, 'rb') as f:
            files = {'audio_file': (os.path.basename(audio_file_path), f, 'audio/wav')}
            data = {
                'voice_name': voice_name,
                'display_name': display_name,
                'language': language
            }
            response = requests.post(
                f"{base_url}/api/v1/voices",
                headers={"X-API-Key": api_key},
                files=files,
                data=data,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            print(f"✅ Successfully added voice: {voice_name}")
            print(f"   Display Name: {result.get('voice', {}).get('display_name')}")
            print(f"   Language: {result.get('voice', {}).get('language')}")
            print(f"   Public URL: {result.get('voice', {}).get('public_url', '')[:60]}...")
            return result
    except Exception as e:
        print(f"❌ Failed to add voice: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        return None

def update_voice(base_url, api_key, voice_name, display_name=None, language=None, audio_file_path=None):
    """Update an existing voice"""
    print("\n" + "="*80)
    print(f"🔄 UPDATING VOICE: {voice_name}")
    print("="*80)
    
    try:
        data = {}
        if display_name:
            data['display_name'] = display_name
        if language:
            data['language'] = language
        
        files = None
        if audio_file_path and os.path.exists(audio_file_path):
            files = {'audio_file': (os.path.basename(audio_file_path), open(audio_file_path, 'rb'), 'audio/wav')}
        
        response = requests.put(
            f"{base_url}/api/v1/voices/{voice_name}",
            headers={"X-API-Key": api_key},
            files=files,
            data=data,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        print(f"✅ Successfully updated voice: {voice_name}")
        print(f"   Display Name: {result.get('voice', {}).get('display_name')}")
        print(f"   Language: {result.get('voice', {}).get('language')}")
        return result
    except Exception as e:
        print(f"❌ Failed to update voice: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        return None
    finally:
        if files and files.get('audio_file'):
            files['audio_file'][1].close()

def delete_voice(base_url, api_key, voice_name):
    """Delete a voice"""
    print("\n" + "="*80)
    print(f"🗑️  DELETING VOICE: {voice_name}")
    print("="*80)
    try:
        response = requests.delete(
            f"{base_url}/api/v1/voices/{voice_name}",
            headers={"X-API-Key": api_key},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        print(f"✅ Successfully deleted voice: {voice_name}")
        return result
    except Exception as e:
        print(f"❌ Failed to delete voice: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        return None

def create_tts_task(base_url, api_key, text, voice_name, source_language="en"):
    """Create a TTS task using the voice"""
    print("\n" + "="*80)
    print("🎵 CREATING TTS TASK")
    print("="*80)
    try:
        data = {
            'text': text,
            'source_language': source_language,
            'voice_name': voice_name,
            'priority': 'normal',
            'model_id': 'tts_models/multilingual/multi-dataset/xtts_v2'
        }
        response = requests.post(
            f"{base_url}/api/v1/tts",
            headers={"X-API-Key": api_key},
            data=data,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        task_id = result.get('task_id')
        print(f"✅ Successfully created TTS task")
        print(f"   Task ID: {task_id}")
        print(f"   Voice: {voice_name}")
        print(f"   Text: {text[:50]}...")
        print(f"   Status: {result.get('status', 'unknown')}")
        return result
    except Exception as e:
        print(f"❌ Failed to create TTS task: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        return None

def main():
    """Main test function"""
    print("\n" + "="*80)
    print("🎤 VOICE MANAGEMENT AND TTS TASK TEST")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {API_KEY[:20]}...")
    
    # Check server
    if not check_server(BASE_URL):
        print(f"❌ Server at {BASE_URL} is not accessible")
        sys.exit(1)
    print("✅ Server is accessible")
    
    # Step 1: List existing voices
    list_voices(BASE_URL, API_KEY)
    
    # Step 2: Add a voice
    add_result = add_voice(BASE_URL, API_KEY, VOICE_NAME, DISPLAY_NAME, LANGUAGE, AUDIO_FILE_PATH)
    if not add_result:
        print("❌ Failed to add voice, cannot continue")
        sys.exit(1)
    
    # Step 3: List voices again to confirm
    list_voices(BASE_URL, API_KEY)
    
    # Step 4: Update the voice
    update_voice(BASE_URL, API_KEY, VOICE_NAME, display_name="Updated Test Voice Alice", language="en")
    
    # Step 5: Create a TTS task using the voice
    tts_text = "Hello, this is a test of the text-to-speech system using the newly created voice."
    tts_result = create_tts_task(BASE_URL, API_KEY, tts_text, VOICE_NAME, "en")
    
    if tts_result:
        task_id = tts_result.get('task_id')
        print(f"\n✅ TTS task created successfully!")
        print(f"   You can check the task status at: {BASE_URL}/api/v1/task/{task_id}/status")
        print(f"   You can get the result at: {BASE_URL}/api/v1/tts/{task_id}/result")
    
    # Step 6: Optionally delete the voice (commented out to keep it for testing)
    # delete_voice(BASE_URL, API_KEY, VOICE_NAME)
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETED")
    print("="*80)

if __name__ == "__main__":
    main()

