#!/usr/bin/env python3
"""
Script to create a TTS task directly in the PostgreSQL database.
Uses the same approach as create_task_direct_db.py for transcription tasks.
"""

import sys
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Add proxy_server to path
_proxy_server_path = os.path.join(_project_root, 'proxy_server')
if _proxy_server_path not in sys.path:
    sys.path.insert(0, _proxy_server_path)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy import text as sql_text
import json

# Configuration
TEXT = "I am Tobius the great man from Iganga and Tanzania Bukoba , kammpala , masaka . We sign great work and make it work all over the world"
MODEL_ID = "tts_models/multilingual/multi-dataset/xtts_v2"
SOURCE_LANGUAGE = "en"
TASK_TYPE = "TTS"  # Enum values are uppercase
PRIORITY = "NORMAL"  # Enum values are uppercase
REQUIRED_MINER_COUNT = 3
MIN_MINER_COUNT = 1
MAX_MINER_COUNT = 5

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
    print_section(f"Step 1: Getting Voice Information")
    print(f"   Voice Name: {voice_name}")
    
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
                print(f"✅ Voice found: {display_name}")
                print(f"   Language: {language}")
                print(f"   Public URL: {public_url[:60]}...")
                
                return {
                    'voice_name': voice_name_db,
                    'display_name': display_name,
                    'language': language,
                    'public_url': public_url
                }
            else:
                print(f"❌ Voice '{voice_name}' not found in database")
                return None
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error getting voice: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_text_content(text: str, source_language: str) -> str:
    """Create a text content record in the database and return content_id"""
    print_section("Step 2: Creating Text Content Record")
    
    print(f"   Text length: {len(text)} characters")
    print(f"   Language: {source_language}")
    
    # Generate content_id
    content_id = str(uuid.uuid4())
    print(f"   Generated Content ID: {content_id}")
    
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
            # Insert text content record (table is 'text_content', not 'text_contents')
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
            
            print(f"✅ Text content record created successfully!")
            print(f"   Content ID: {content_id}")
            
            return content_id
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error creating text content: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_tts_task(content_id: str, voice_info: dict, model_id: str, source_language: str) -> str:
    """Create a TTS task in the database and return task_id"""
    print_section("Step 3: Creating TTS Task")
    
    # Generate task_id
    task_id = str(uuid.uuid4())
    print(f"   Generated Task ID: {task_id}")
    print(f"   Content ID: {content_id}")
    print(f"   Voice: {voice_info['voice_name']}")
    print(f"   Model: {model_id}")
    print(f"   Language: {source_language}")
    print(f"   Type: {TASK_TYPE}")
    print(f"   Priority: {PRIORITY}")
    print(f"   Required Miners: {REQUIRED_MINER_COUNT}")
    
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
            # Insert task record (tasks table only has input_text_id, not input_text)
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
                    NOW(),
                    NOW()
                )
            """)
            
            params = {
                'task_id': task_id,
                'task_type': TASK_TYPE,  # TTS (uppercase enum)
                'status': 'PENDING',  # Start as PENDING, will be assigned by validator
                'priority': PRIORITY,  # NORMAL (uppercase enum)
                'input_text_id': content_id,  # Reference to text_content table
                'model_id': model_id,
                'source_language': source_language,
                'voice_name': voice_info['voice_name'],
                'speaker_wav_url': voice_info['public_url'],
                'required_miner_count': REQUIRED_MINER_COUNT,
                'min_miner_count': MIN_MINER_COUNT,
                'max_miner_count': MAX_MINER_COUNT
            }
            
            conn.execute(insert_query, params)
            conn.commit()
            
            print(f"✅ TTS task created successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Status: pending (will be assigned by validator)")
            
            return task_id
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error creating task: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function"""
    print_section("Create TTS Task Directly in Database")
    print(f"Text: {TEXT[:50]}...")
    print(f"Model: {MODEL_ID}")
    print(f"Language: {SOURCE_LANGUAGE}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Step 1: Get voice information
    voice_name = "english_alice"  # From database check earlier
    voice_info = get_voice_info(voice_name)
    if not voice_info:
        print("\n❌ Failed to get voice information. Cannot create task.")
        print("   Available voices can be checked in the database")
        return
    
    # Step 2: Create text content record
    content_id = create_text_content(TEXT, SOURCE_LANGUAGE)
    if not content_id:
        print("\n❌ Failed to create text content record. Cannot create task.")
        return
    
    # Step 3: Create task
    task_id = create_tts_task(content_id, voice_info, MODEL_ID, SOURCE_LANGUAGE)
    if not task_id:
        print("\n❌ Failed to create task.")
        return
    
    # Summary
    print_section("✅ SUCCESS!")
    print(f"Task ID: {task_id}")
    print(f"Content ID: {content_id}")
    print(f"Model: {MODEL_ID}")
    print(f"Language: {SOURCE_LANGUAGE}")
    print(f"Voice: {voice_info['voice_name']}")
    print(f"Status: pending")
    print(f"\n⚠️  Important Notes:")
    print(f"   1. Text content record created in database")
    print(f"   2. TTS task created and ready for assignment")
    print(f"   3. Validator will pick up this task and assign it to miners")
    print(f"\nYou can check the task using:")
    print(f"   python3 check_task.py {task_id}")
    print(f"   Or query: SELECT * FROM tasks WHERE task_id = '{task_id}';")
    print("=" * 80)

if __name__ == "__main__":
    main()

