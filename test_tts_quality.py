#!/usr/bin/env python3
"""
Test script for TTS quality - creates a task, waits for completion, and retrieves audio
"""

import sys
import os
import time
import asyncio
from datetime import datetime

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy import text as sql_text
import json
import uuid

def get_database_url():
    """Get database URL from environment or use default"""
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

def print_section(title: str):
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")

def get_voice_info(voice_name: str):
    """Get voice information from database"""
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
            query = sql_text("""
                SELECT 
                    voice_name,
                    display_name,
                    language,
                    public_url
                FROM voices
                WHERE voice_name = :voice_name
            """)
            
            result = conn.execute(query, {'voice_name': voice_name})
            voice = result.fetchone()
            
            if voice:
                voice_name_db, display_name, language, public_url = voice
                return {
                    'voice_name': voice_name_db,
                    'display_name': display_name,
                    'language': language,
                    'public_url': public_url
                }
            else:
                return None
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error getting voice: {e}")
        return None

def create_text_content(text: str, source_language: str) -> str:
    """Create a text content record in the database and return content_id"""
    content_id = str(uuid.uuid4())
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
            insert_query = sql_text("""
                INSERT INTO text_content (
                    content_id,
                    text,
                    source_language,
                    detected_language,
                    language_confidence,
                    text_length,
                    word_count,
                    meta_data,
                    created_at,
                    updated_at
                ) VALUES (
                    :content_id,
                    :text,
                    :source_language,
                    :detected_language,
                    :language_confidence,
                    :text_length,
                    :word_count,
                    CAST(:meta_data AS jsonb),
                    NOW(),
                    NOW()
                )
            """)
            
            word_count = len(text.split())
            meta_data = {
                'original_source_language': source_language,
                'detection_method': 'manual'
            }
            
            params = {
                'content_id': content_id,
                'text': text,
                'source_language': source_language,
                'detected_language': source_language,
                'language_confidence': 1.0,
                'text_length': len(text),
                'word_count': word_count,
                'meta_data': json.dumps(meta_data)
            }
            
            conn.execute(insert_query, params)
            conn.commit()
            
            return content_id
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error creating text content: {e}")
        return None

def create_tts_task(content_id: str, voice_info: dict, model_id: str, source_language: str, miners: list) -> str:
    """Create a TTS task in the database and return task_id"""
    task_id = str(uuid.uuid4())
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
            insert_query = sql_text("""
                INSERT INTO tasks (
                    task_id,
                    task_type,
                    status,
                    priority,
                    input_text_id,
                    model_id,
                    source_language,
                    voice_name,
                    speaker_wav_url,
                    required_miner_count,
                    min_miner_count,
                    max_miner_count,
                    assigned_miners,
                    actual_miner_count,
                    created_at,
                    updated_at
                ) VALUES (
                    :task_id,
                    :task_type,
                    :status,
                    :priority,
                    :input_text_id,
                    :model_id,
                    :source_language,
                    :voice_name,
                    :speaker_wav_url,
                    :required_miner_count,
                    :min_miner_count,
                    :max_miner_count,
                    :assigned_miners,
                    :actual_miner_count,
                    NOW(),
                    NOW()
                )
            """)
            
            params = {
                'task_id': task_id,
                'task_type': 'TTS',
                'status': 'ASSIGNED',
                'priority': 'NORMAL',
                'input_text_id': content_id,
                'model_id': model_id,
                'source_language': source_language,
                'voice_name': voice_info['voice_name'],
                'speaker_wav_url': voice_info['public_url'],
                'required_miner_count': len(miners),
                'min_miner_count': 1,
                'max_miner_count': len(miners),
                'assigned_miners': miners,
                'actual_miner_count': len(miners)
            }
            
            conn.execute(insert_query, params)
            conn.commit()
            
            return task_id
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error creating task: {e}")
        return None

def check_task_status(task_id: str):
    """Check task status and return task info"""
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
            query = sql_text("""
                SELECT 
                    task_id,
                    task_type::text as task_type,
                    status::text as status,
                    miner_responses,
                    best_response,
                    completed_at
                FROM tasks
                WHERE task_id = :task_id
            """)
            
            result = conn.execute(query, {'task_id': task_id})
            task = result.fetchone()
            
            if task:
                return {
                    'task_id': task[0],
                    'task_type': task[1],
                    'status': task[2],
                    'miner_responses': task[3],
                    'best_response': task[4],
                    'completed_at': task[5]
                }
            return None
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error checking task: {e}")
        return None

def get_audio_url_from_response(miner_response: dict):
    """Extract audio file URL from miner response"""
    try:
        response_data = miner_response.get('response', {}).get('response_data', {})
        output_data = response_data.get('output_data', {})
        audio_file = output_data.get('audio_file', {})
        
        # Try to get public_url or file_url
        public_url = audio_file.get('public_url')
        file_url = audio_file.get('file_url')
        file_id = audio_file.get('file_id')
        
        if public_url:
            return public_url
        elif file_id:
            # Construct URL from file_id
            return f"https://pub-06f0e98c01284240a79c03c4a59d4175.r2.dev/tts_audio/{file_id}"
        elif file_url:
            return f"https://violet-proxy-bl4w.onrender.com{file_url}"
        
        return None
    except Exception as e:
        print(f"   Error extracting URL: {e}")
        return None

def get_file_url_from_db(file_id: str):
    """Get file public URL from database"""
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
            query = sql_text("""
                SELECT public_url, r2_key
                FROM files
                WHERE file_id = :file_id
            """)
            
            result = conn.execute(query, {'file_id': file_id})
            file = result.fetchone()
            
            if file:
                public_url = file[0]
                if public_url:
                    return public_url
                # If no public_url, try to construct from r2_key
                r2_key = file[1]
                if r2_key:
                    return f"https://pub-06f0e98c01284240a79c03c4a59d4175.r2.dev/{r2_key}"
            return None
        
        engine.dispose()
        
    except Exception as e:
        print(f"   Error getting file URL: {e}")
        return None

async def wait_for_task_completion(task_id: str, max_wait_minutes: int = 10, check_interval: int = 10):
    """Wait for task to complete and return responses"""
    print_section("Waiting for Task Completion")
    print(f"Task ID: {task_id}")
    print(f"Max wait time: {max_wait_minutes} minutes")
    print(f"Check interval: {check_interval} seconds")
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_seconds:
            print(f"\n⏱️  Timeout after {max_wait_minutes} minutes")
            return None
        
        task_info = check_task_status(task_id)
        if not task_info:
            print(f"❌ Task not found")
            return None
        
        status = task_info['status']
        print(f"\n[{elapsed:.0f}s] Status: {status}")
        
        if status == 'COMPLETED':
            print(f"✅ Task completed!")
            return task_info
        elif status in ['FAILED', 'CANCELLED']:
            print(f"❌ Task {status.lower()}")
            return task_info
        
        miner_responses = task_info.get('miner_responses')
        if miner_responses:
            response_count = len(miner_responses) if isinstance(miner_responses, list) else 0
            print(f"   Responses: {response_count}")
        
        print(f"   Waiting {check_interval}s before next check...")
        await asyncio.sleep(check_interval)

async def main():
    print_section("TTS Quality Test Script")
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Test parameters
    TEST_TEXT = "Hello, this is a quality test for text-to-speech. We want to verify that the voice cloning works correctly and produces natural-sounding speech."
    VOICE_NAME = "english_alice"
    MODEL_ID = "tts_models/multilingual/multi-dataset/xtts_v2"
    SOURCE_LANGUAGE = "en"
    TEST_MINERS = [6, 16]  # Miners to test with
    
    print(f"\n📋 Test Parameters:")
    print(f"   Text: {TEST_TEXT[:60]}...")
    print(f"   Voice: {VOICE_NAME}")
    print(f"   Model: {MODEL_ID}")
    print(f"   Language: {SOURCE_LANGUAGE}")
    print(f"   Miners: {TEST_MINERS}")
    
    # Step 1: Get voice info
    print_section("Step 1: Getting Voice Information")
    voice_info = get_voice_info(VOICE_NAME)
    if not voice_info:
        print(f"❌ Voice '{VOICE_NAME}' not found")
        return
    print(f"✅ Voice found: {voice_info['display_name']}")
    print(f"   Language: {voice_info['language']}")
    
    # Step 2: Create text content
    print_section("Step 2: Creating Text Content")
    content_id = create_text_content(TEST_TEXT, SOURCE_LANGUAGE)
    if not content_id:
        print(f"❌ Failed to create text content")
        return
    print(f"✅ Text content created: {content_id}")
    
    # Step 3: Create TTS task
    print_section("Step 3: Creating TTS Task")
    task_id = create_tts_task(content_id, voice_info, MODEL_ID, SOURCE_LANGUAGE, TEST_MINERS)
    if not task_id:
        print(f"❌ Failed to create task")
        return
    print(f"✅ TTS task created: {task_id}")
    print(f"   Assigned to miners: {TEST_MINERS}")
    
    # Step 4: Wait for completion
    task_info = await wait_for_task_completion(task_id, max_wait_minutes=10)
    
    if not task_info:
        print(f"\n❌ Task did not complete in time")
        return
    
    # Step 5: Extract audio URLs
    print_section("Step 5: Extracting Audio URLs")
    miner_responses = task_info.get('miner_responses', [])
    
    if not miner_responses:
        print(f"❌ No miner responses found")
        return
    
    print(f"✅ Found {len(miner_responses)} response(s)\n")
    
    audio_urls = []
    for i, response in enumerate(miner_responses, 1):
        miner_uid = response.get('miner_uid', 'Unknown')
        print(f"Response {i} (Miner {miner_uid}):")
        
        # Try to get URL from response
        audio_url = get_audio_url_from_response(response)
        
        # If not found, try to get from file_id
        if not audio_url:
            try:
                response_data = response.get('response', {}).get('response_data', {})
                output_data = response_data.get('output_data', {})
                audio_file = output_data.get('audio_file', {})
                file_id = audio_file.get('file_id')
                
                if file_id:
                    audio_url = get_file_url_from_db(file_id)
            except:
                pass
        
        if audio_url:
            print(f"   ✅ Audio URL: {audio_url}")
            audio_urls.append({
                'miner_uid': miner_uid,
                'url': audio_url
            })
        else:
            print(f"   ⚠️  Could not extract audio URL")
    
    # Final summary
    print_section("✅ TEST COMPLETE")
    print(f"Task ID: {task_id}")
    print(f"Status: {task_info['status']}")
    print(f"\n🎵 Audio Files Generated:")
    
    if audio_urls:
        for i, audio_info in enumerate(audio_urls, 1):
            print(f"\n   Audio {i} (Miner {audio_info['miner_uid']}):")
            print(f"   🌐 URL: {audio_info['url']}")
            print(f"   💡 Open in browser or download to listen")
    else:
        print(f"   ❌ No audio URLs found")
    
    print(f"\n📊 Quality Assessment:")
    print(f"   1. Open each URL in a browser")
    print(f"   2. Listen to the audio")
    print(f"   3. Check for:")
    print(f"      - Natural voice quality")
    print(f"      - Proper pronunciation")
    print(f"      - Voice cloning accuracy")
    print(f"      - Audio clarity")
    print(f"      - Appropriate pacing and intonation")
    
    print(f"\n{'=' * 80}")

if __name__ == "__main__":
    asyncio.run(main())
