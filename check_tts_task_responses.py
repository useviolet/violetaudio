#!/usr/bin/env python3
"""
Check TTS tasks for responses and extract audio URLs
"""

import sys
import os
from pathlib import Path

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
import json

BASE_URL = "https://violet-proxy-bl4w.onrender.com"

def get_database_url():
    """Get database URL from environment or use default"""
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

def get_file_public_url(file_id: str):
    """Get public URL for a file from database"""
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
                SELECT public_url, original_filename, file_size
                FROM files
                WHERE file_id = CAST(:file_id AS uuid)
            """)
            
            result = conn.execute(query, {'file_id': file_id})
            file_info = result.fetchone()
            
            if file_info:
                return {
                    'public_url': file_info[0],
                    'filename': file_info[1],
                    'file_size': file_info[2]
                }
            return None
        
        engine.dispose()
    except Exception as e:
        print(f"⚠️  Error querying file: {e}")
        return None

def check_task_responses(task_ids):
    """Check tasks for responses and extract audio URLs"""
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
        
        results = {}
        
        with engine.connect() as conn:
            for task_id, model_name in task_ids.items():
                print(f"\n{'=' * 80}")
                print(f"  TASK: {model_name}")
                print(f"{'=' * 80}")
                print(f"Task ID: {task_id}")
                
                # Get task info
                query = text("""
                    SELECT 
                        task_id,
                        task_type::text,
                        status::text,
                        model_id,
                        miner_responses,
                        created_at,
                        updated_at
                    FROM tasks
                    WHERE task_id = CAST(:task_id AS uuid)
                """)
                
                result = conn.execute(query, {'task_id': task_id})
                task = result.fetchone()
                
                if not task:
                    print(f"❌ Task not found")
                    results[task_id] = {
                        'model': model_name,
                        'status': 'NOT_FOUND',
                        'audio_urls': []
                    }
                    continue
                
                task_type = task[1]
                status = task[2]
                model_id = task[3]
                miner_responses = task[4]
                created_at = task[5]
                updated_at = task[6]
                
                print(f"Status: {status}")
                print(f"Model ID: {model_id}")
                print(f"Created: {created_at}")
                print(f"Updated: {updated_at}")
                
                audio_urls = []
                
                if miner_responses and isinstance(miner_responses, list) and len(miner_responses) > 0:
                    print(f"\n✅ Found {len(miner_responses)} response(s)")
                    
                    for idx, response in enumerate(miner_responses, 1):
                        if isinstance(response, dict):
                            miner_uid = response.get('miner_uid', 'Unknown')
                            response_data = response.get('response', {}).get('response_data', {})
                            output_data = response_data.get('output_data', {})
                            audio_file = output_data.get('audio_file', {})
                            file_id = audio_file.get('file_id')
                            file_name = audio_file.get('file_name', '')
                            processing_time = response_data.get('processing_time', 0.0)
                            
                            print(f"\n  Response #{idx} (Miner UID: {miner_uid}):")
                            print(f"    Processing Time: {processing_time:.2f}s")
                            
                            if file_id:
                                print(f"    File ID: {file_id}")
                                
                                # Get public URL from database
                                file_info = get_file_public_url(file_id)
                                
                                if file_info and file_info.get('public_url'):
                                    public_url = file_info['public_url']
                                    filename = file_info.get('filename', file_name) or f"{file_id}.wav"
                                    file_size = file_info.get('file_size', 0)
                                    
                                    print(f"    ✅ Audio File:")
                                    print(f"       URL: {public_url}")
                                    print(f"       Filename: {filename}")
                                    if file_size:
                                        print(f"       Size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
                                    
                                    audio_urls.append({
                                        'url': public_url,
                                        'filename': filename,
                                        'file_id': file_id,
                                        'miner_uid': miner_uid,
                                        'processing_time': processing_time,
                                        'file_size': file_size
                                    })
                                else:
                                    # Fallback to proxy server URL
                                    proxy_url = f"{BASE_URL}/api/v1/tts/audio/{file_id}"
                                    print(f"    ⚠️  Audio File (using proxy URL):")
                                    print(f"       URL: {proxy_url}")
                                    print(f"       Filename: {file_name or f'{file_id}.wav'}")
                                    
                                    audio_urls.append({
                                        'url': proxy_url,
                                        'filename': file_name or f"{file_id}.wav",
                                        'file_id': file_id,
                                        'miner_uid': miner_uid,
                                        'processing_time': processing_time,
                                        'file_size': 0
                                    })
                            else:
                                error = output_data.get('error', 'Unknown error')
                                print(f"    ❌ No audio file (Error: {error})")
                else:
                    print(f"\n⚠️  No responses yet")
                    audio_urls = []
                
                results[task_id] = {
                    'model': model_name,
                    'status': status,
                    'model_id': model_id,
                    'response_count': len(miner_responses) if miner_responses else 0,
                    'audio_urls': audio_urls
                }
        
        engine.dispose()
        return results
        
    except Exception as e:
        print(f"❌ Error querying tasks: {e}")
        import traceback
        traceback.print_exc()
        return {}

def main():
    # Task IDs from the created TTS tasks
    task_ids = {
        '6df450ae-7056-41e4-842b-af1abf24921a': 'tts_models/multilingual/multi-dataset/xtts_v2',
        'b3571621-63c1-4d36-921b-fad7cab9f51a': 'tts_models/multilingual/multi-dataset/your_tts',
        'b09cbfa7-f5ce-4fea-8f86-8189435ce895': 'tts_models/en/ljspeech/tacotron2-DDC',
        'dac0f55b-44be-4d1a-b2d1-4a57433131d2': 'tts_models/en/vctk/vits'
    }
    
    print("\n" + "=" * 80)
    print("  TTS TASK RESPONSE CHECKER")
    print("=" * 80)
    
    results = check_task_responses(task_ids)
    
    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY - AUDIO FILE URLs")
    print("=" * 80)
    
    total_responses = 0
    total_audio_files = 0
    
    for task_id, info in results.items():
        model = info['model']
        status = info['status']
        response_count = info.get('response_count', 0)
        audio_urls = info.get('audio_urls', [])
        
        total_responses += response_count
        total_audio_files += len(audio_urls)
        
        print(f"\n📋 {model}")
        print(f"   Task ID: {task_id}")
        print(f"   Status: {status}")
        print(f"   Responses: {response_count}")
        print(f"   Audio Files: {len(audio_urls)}")
        
        if audio_urls:
            for idx, audio_info in enumerate(audio_urls, 1):
                print(f"\n   Audio #{idx}:")
                print(f"      URL: {audio_info['url']}")
                print(f"      Filename: {audio_info['filename']}")
                print(f"      Miner UID: {audio_info['miner_uid']}")
                if audio_info.get('file_size'):
                    print(f"      Size: {audio_info['file_size']:,} bytes")
        else:
            print(f"   ⚠️  No audio files available")
    
    print(f"\n{'=' * 80}")
    print(f"Total Responses: {total_responses}")
    print(f"Total Audio Files: {total_audio_files}")
    print(f"{'=' * 80}")
    
    # Print all URLs in a simple list format
    if total_audio_files > 0:
        print(f"\n📥 All Audio URLs:")
        print()
        for task_id, info in results.items():
            for audio_info in info.get('audio_urls', []):
                print(audio_info['url'])
                print(f"  # {audio_info['filename']} (Miner {audio_info['miner_uid']})")
                print()

if __name__ == "__main__":
    main()
