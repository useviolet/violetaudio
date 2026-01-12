#!/usr/bin/env python3
"""
Script to create a TTS task using the same approach as transcription tasks
Uses /api/v1/tts endpoint with form data
"""

import os
import sys
import httpx
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
PROXY_SERVER_URL = "https://violet-proxy-bl4w.onrender.com"
TEXT = "I am Tobius the great man from Iganga and Tanzania Bukoba , kammpala , masaka . We sign great work and make it work all over the world"
MODEL_ID = "tts_models/multilingual/multi-dataset/xtts_v2"
SOURCE_LANGUAGE = "en"
PRIORITY = "normal"

# Use provided API key
API_KEY = "tQlbLPoTF7RRsvJjgCm_4kHiIg-xqoQ6l4utqW56sY0"

if not API_KEY:
    print("❌ Error: API key not found!")
    sys.exit(1)

def get_headers():
    """Get authentication headers"""
    return {
        "X-API-Key": API_KEY
    }

async def create_tts_task_with_text(text: str, voice_name: str, model_id: str, source_language: str, priority: str = "normal") -> dict:
    """Create TTS task using /api/v1/tts endpoint (same pattern as transcription)"""
    print(f"\n📤 Creating TTS task with text")
    print(f"   Text length: {len(text)} characters")
    print(f"   Voice: {voice_name}")
    print(f"   Model: {model_id}")
    print(f"   Language: {source_language}")
    print(f"   Priority: {priority}")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = get_headers()
            
            # Prepare form data for TTS endpoint (same pattern as transcription)
            data = {
                'text': text,
                'voice_name': voice_name,
                'model_id': model_id,
                'source_language': source_language,
                'priority': priority
            }
            
            endpoint = f"{PROXY_SERVER_URL}/api/v1/tts"
            print(f"   Endpoint: {endpoint}")
            print(f"   Sending request...")
            
            response = await client.post(
                endpoint,
                headers=headers,
                data=data  # Form data, not files
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                task_id = result.get("task_id") or result.get("id")
                
                print(f"✅ TTS task created successfully!")
                print(f"   Task ID: {task_id}")
                
                return {
                    "task_id": task_id,
                    "status": result.get("status", "created"),
                    "result": result
                }
            else:
                print(f"❌ Task creation failed with status {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
    except httpx.TimeoutException:
        print(f"❌ Request timeout")
        return None
    except Exception as e:
        print(f"❌ Error creating task: {e}")
        import traceback
        traceback.print_exc()
        return None


async def get_voice_from_db():
    """Get available voice from database"""
    print("\n📋 Checking database for available voices...")
    
    try:
        from sqlalchemy import create_engine, text
        
        database_url = os.getenv(
            'DATABASE_URL',
            'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
        )
        
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
                SELECT voice_name, display_name, language
                FROM voices
                ORDER BY created_at DESC
                LIMIT 1
            """)
            
            result = conn.execute(query)
            voice = result.fetchone()
            
            if voice:
                voice_name, display_name, language = voice
                print(f"✅ Found voice: {voice_name} ({display_name})")
                return voice_name
            else:
                print("⚠️  No voices found in database")
                return None
        
        engine.dispose()
        
    except Exception as e:
        print(f"⚠️  Could not check database: {e}")
        return None


async def main():
    """Main function to create TTS task"""
    print("=" * 80)
    print("🎯 Creating TTS Task")
    print("=" * 80)
    print(f"Proxy Server: {PROXY_SERVER_URL}")
    print(f"Text: {TEXT[:50]}...")
    print(f"Model: {MODEL_ID}")
    print(f"Language: {SOURCE_LANGUAGE}")
    print("=" * 80)
    
    # Get voice from database
    voice_name = await get_voice_from_db()
    
    if not voice_name:
        # Check command line for voice name
        if len(sys.argv) > 1:
            voice_name = sys.argv[1]
            print(f"\n🎤 Using voice from command line: {voice_name}")
        else:
            print("\n❌ No voice found. Please:")
            print("   1. Add a voice using the voice management API, or")
            print("   2. Specify voice_name as argument: python3 create_tts_task_simple.py <voice_name>")
            return
    
    # Create TTS task
    task_info = await create_tts_task_with_text(
        TEXT,
        voice_name,
        MODEL_ID,
        SOURCE_LANGUAGE,
        PRIORITY
    )
    
    if not task_info:
        print("\n❌ Failed to create TTS task.")
        return
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ SUCCESS!")
    print("=" * 80)
    print(f"Task ID: {task_info['task_id']}")
    print(f"Model: {MODEL_ID}")
    print(f"Language: {SOURCE_LANGUAGE}")
    print(f"Voice: {voice_name}")
    print(f"Status: {task_info.get('status', 'created')}")
    print("\nYou can check the task result using:")
    print(f"  GET {PROXY_SERVER_URL}/api/v1/tts/{task_info['task_id']}/result")
    print("=" * 80)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

