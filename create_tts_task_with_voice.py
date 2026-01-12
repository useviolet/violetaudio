#!/usr/bin/env python3
"""
Create a TTS task using the specified model and text
Checks database for available voices if API access is limited
"""

import sys
import os
import requests
from dotenv import load_dotenv

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Add proxy_server to path for database imports
_proxy_server_path = os.path.join(_project_root, 'proxy_server')
if _proxy_server_path not in sys.path:
    sys.path.insert(0, _proxy_server_path)

# Load environment variables
load_dotenv()

from sqlalchemy import create_engine, text

# Configuration
BASE_URL = "https://violet-proxy-bl4w.onrender.com"
# Use provided API key
API_KEY = "tQlbLPoTF7RRsvJjgCm_4kHiIg-xqoQ6l4utqW56sY0"

# Task parameters
TEXT = "I am Tobius the great man from Iganga and Tanzania Bukoba , kammpala , masaka . We sign great work and make it work all over the world"
MODEL_ID = "tts_models/multilingual/multi-dataset/xtts_v2"
SOURCE_LANGUAGE = "en"
PRIORITY = "normal"

def get_database_url():
    """Get database URL from environment or use default"""
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

def get_available_voices_from_db():
    """Get list of available voices from the database"""
    print("\n" + "=" * 80)
    print("  GETTING AVAILABLE VOICES FROM DATABASE")
    print("=" * 80)
    
    database_url = get_database_url()
    
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 10,
                "sslmode": "require"
            }
        )
        
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    voice_name,
                    display_name,
                    language,
                    public_url,
                    created_at
                FROM voices
                ORDER BY created_at DESC
                LIMIT 20
            """)
            
            result = conn.execute(query)
            voices = result.fetchall()
            
            if voices:
                print(f"\n✅ Found {len(voices)} available voice(s) in database:\n")
                
                voice_list = []
                for i, voice in enumerate(voices, 1):
                    (voice_name, display_name, language, public_url, created_at) = voice
                    print(f"   {i}. Voice Name: {voice_name}")
                    print(f"      Display Name: {display_name or 'N/A'}")
                    print(f"      Language: {language or 'N/A'}")
                    print(f"      Created: {created_at}")
                    print()
                    
                    voice_list.append({
                        'voice_name': voice_name,
                        'display_name': display_name,
                        'language': language,
                        'public_url': public_url
                    })
                
                return voice_list
            else:
                print("\n⚠️  No voices found in database")
                print("   You may need to add a voice first using the voice management API")
                return []
        
        engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Error getting voices from database: {e}")
        import traceback
        traceback.print_exc()
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
        "model_id": model_id,
        "source_language": source_language,
        "priority": priority
    }
    
    # Add voice_name if provided
    if voice_name:
        form_data["voice_name"] = voice_name
    
    print(f"\n📝 Task Parameters:")
    print(f"   Text: {text[:50]}... (length: {len(text)} chars)")
    print(f"   Voice Name: {voice_name or 'None (will use default)'}")
    print(f"   Model ID: {model_id}")
    print(f"   Source Language: {source_language}")
    print(f"   Priority: {priority}")
    
    try:
        response = requests.post(url, headers=headers, data=form_data, timeout=30)
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
            
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error creating TTS task: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"   Error Detail: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"   Response: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating TTS task: {e}")
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
    
    # Step 1: Get available voices from database
    voices = get_available_voices_from_db()
    
    # Step 2: Select a voice
    voice_name = None
    if voices:
        # Use first available voice
        selected_voice = voices[0]
        voice_name = selected_voice.get('voice_name')
        
        print(f"\n🎤 Selected Voice: {voice_name}")
        print(f"   Display Name: {selected_voice.get('display_name', 'N/A')}")
        print(f"   Language: {selected_voice.get('language', 'N/A')}")
        
        # Allow override from command line
        if len(sys.argv) > 1:
            voice_name = sys.argv[1]
            print(f"\n   Overriding with command line voice_name: {voice_name}")
    else:
        # Check for voice_name in command line args
        if len(sys.argv) > 1:
            voice_name = sys.argv[1]
            print(f"\n🎤 Using voice_name from command line: {voice_name}")
        else:
            print("\n⚠️  No voices found in database and no voice_name provided")
            print("   The API will try to use a default voice if available")
            print("   Or you can specify a voice_name as a command line argument:")
            print("   python3 create_tts_task_with_voice.py <voice_name>")
    
    # Step 3: Create TTS task
    task_id = create_tts_task(
        text=TEXT,
        voice_name=voice_name,
        model_id=MODEL_ID,
        source_language=SOURCE_LANGUAGE,
        priority=PRIORITY
    )
    
    if task_id:
        print(f"\n✅ Task creation completed successfully!")
        print(f"   Task ID: {task_id}")
    else:
        print(f"\n❌ Task creation failed")
        print(f"\n   Troubleshooting:")
        print(f"   1. Check that your API key has 'client' or 'admin' role")
        print(f"   2. Verify the voice_name exists in the database")
        print(f"   3. Check API documentation at: {BASE_URL}/docs")

if __name__ == "__main__":
    main()

