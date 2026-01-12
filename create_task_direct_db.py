#!/usr/bin/env python3
"""
Script to create a transcription task directly in the PostgreSQL database.
Uploads file first, then creates the task.
"""

import sys
import os
import uuid
import base64
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
import json

# Configuration
AUDIO_FILE_PATH = "/Users/user/Documents/Jarvis/violet/tests/chatterbox_test_output.wav"
MODEL_ID = "openai/whisper-tiny"
SOURCE_LANGUAGE = "en"
TASK_TYPE = "TRANSCRIPTION"  # Enum values are uppercase
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

def create_file_record(file_path: str) -> str:
    """Create a file record in the database and return file_id"""
    print_section("Step 1: Creating File Record")
    
    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        return None
    
    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)
    
    print(f"   File: {filename}")
    print(f"   Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    
    # Generate file_id
    file_id = str(uuid.uuid4())
    print(f"   Generated File ID: {file_id}")
    
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
            # Insert file record
            # Note: For direct DB insertion, we'll create a placeholder file record
            # The actual file would need to be uploaded to R2 separately
            insert_query = text("""
                INSERT INTO files (
                    file_id,
                    original_filename,
                    safe_filename,
                    file_type,
                    content_type,
                    file_size,
                    storage_location,
                    created_at,
                    updated_at
                ) VALUES (
                    :file_id,
                    :original_filename,
                    :safe_filename,
                    :file_type,
                    :content_type,
                    :file_size,
                    :storage_location,
                    NOW(),
                    NOW()
                )
            """)
            
            # Determine file type and content type
            file_ext = Path(filename).suffix.lower()
            if file_ext in ['.wav', '.mp3', '.m4a', '.flac', '.ogg']:
                file_type = 'audio'
                content_type = f'audio/{file_ext[1:]}' if file_ext != '.m4a' else 'audio/mp4'
            else:
                file_type = 'audio'
                content_type = 'audio/wav'
            
            params = {
                'file_id': file_id,
                'original_filename': filename,
                'safe_filename': filename,
                'file_type': file_type,
                'content_type': content_type,
                'file_size': file_size,
                'storage_location': 'r2'  # Assuming R2 storage
            }
            
            conn.execute(insert_query, params)
            conn.commit()
            
            print(f"✅ File record created successfully!")
            print(f"   File ID: {file_id}")
            print(f"   ⚠️  Note: File record created, but actual file upload to R2")
            print(f"      storage needs to be done separately via API or admin interface")
            
            return file_id
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error creating file record: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_transcription_task(file_id: str, model_id: str, source_language: str) -> str:
    """Create a transcription task in the database and return task_id"""
    print_section("Step 2: Creating Transcription Task")
    
    # Generate task_id
    task_id = str(uuid.uuid4())
    print(f"   Generated Task ID: {task_id}")
    print(f"   File ID: {file_id}")
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
            # Insert task record
            # The columns are stored as text/enum, but we'll let PostgreSQL handle the conversion
            insert_query = text("""
                INSERT INTO tasks (
                    task_id,
                    task_type,
                    status,
                    priority,
                    input_file_id,
                    model_id,
                    source_language,
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
                    :input_file_id,
                    :model_id,
                    :source_language,
                    :required_miner_count,
                    :min_miner_count,
                    :max_miner_count,
                    NOW(),
                    NOW()
                )
            """)
            
            params = {
                'task_id': task_id,
                'task_type': TASK_TYPE,  # TRANSCRIPTION (uppercase enum)
                'status': 'PENDING',  # Start as PENDING, will be assigned by validator
                'priority': PRIORITY,  # NORMAL (uppercase enum)
                'input_file_id': file_id,
                'model_id': model_id,
                'source_language': source_language,
                'required_miner_count': REQUIRED_MINER_COUNT,
                'min_miner_count': MIN_MINER_COUNT,
                'max_miner_count': MAX_MINER_COUNT
            }
            
            conn.execute(insert_query, params)
            conn.commit()
            
            print(f"✅ Transcription task created successfully!")
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
    print_section("Create Transcription Task Directly in Database")
    print(f"Audio File: {AUDIO_FILE_PATH}")
    print(f"Model: {MODEL_ID}")
    print(f"Language: {SOURCE_LANGUAGE}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Step 1: Create file record
    file_id = create_file_record(AUDIO_FILE_PATH)
    if not file_id:
        print("\n❌ Failed to create file record. Cannot create task.")
        return
    
    # Step 2: Create task
    task_id = create_transcription_task(file_id, MODEL_ID, SOURCE_LANGUAGE)
    if not task_id:
        print("\n❌ Failed to create task.")
        return
    
    # Summary
    print_section("✅ SUCCESS!")
    print(f"Task ID: {task_id}")
    print(f"File ID: {file_id}")
    print(f"Model: {MODEL_ID}")
    print(f"Language: {SOURCE_LANGUAGE}")
    print(f"Status: pending")
    print(f"\n⚠️  Important Notes:")
    print(f"   1. File record created in database")
    print(f"   2. Task created and ready for assignment")
    print(f"   3. File needs to be uploaded to R2 storage separately")
    print(f"   4. Validator will pick up this task and assign it to miners")
    print(f"\nYou can check the task using:")
    print(f"   python3 check_task.py (modify task_id in script)")
    print(f"   Or query: SELECT * FROM tasks WHERE task_id = '{task_id}';")
    print("=" * 80)

if __name__ == "__main__":
    main()

