#!/usr/bin/env python3
"""
Download TTS audio file by file_id or task_id
"""

import sys
import os
import requests
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

def get_file_info_from_db(file_id: str):
    """Get file information from database"""
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
                    file_id,
                    public_url,
                    r2_key,
                    storage_location,
                    file_size,
                    original_filename
                FROM files
                WHERE file_id = :file_id
            """)
            
            result = conn.execute(query, {'file_id': file_id})
            file_info = result.fetchone()
            
            if file_info:
                return {
                    'file_id': file_info[0],
                    'public_url': file_info[1],
                    'r2_key': file_info[2],
                    'storage_location': file_info[3],
                    'file_size': file_info[4],
                    'original_filename': file_info[5]
                }
            return None
        
        engine.dispose()
    except Exception as e:
        print(f"⚠️  Error querying database: {e}")
        return None

def get_audio_from_task(task_id: str):
    """Get audio file_id from task"""
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
                SELECT miner_responses
                FROM tasks
                WHERE task_id = :task_id
            """)
            
            result = conn.execute(query, {'task_id': task_id})
            task = result.fetchone()
            
            if task and task[0]:
                miner_responses = task[0]
                if isinstance(miner_responses, list) and len(miner_responses) > 0:
                    # Get first response
                    response = miner_responses[0]
                    if isinstance(response, dict):
                        response_data = response.get('response', {}).get('response_data', {})
                        output_data = response_data.get('output_data', {})
                        audio_file = output_data.get('audio_file', {})
                        file_id = audio_file.get('file_id')
                        return file_id
            
            return None
        
        engine.dispose()
    except Exception as e:
        print(f"⚠️  Error querying task: {e}")
        return None

def download_audio(file_id: str, output_path: str = None):
    """Download audio file by file_id"""
    print(f"\n{'=' * 80}")
    print(f"  DOWNLOADING AUDIO FILE")
    print(f"{'=' * 80}")
    print(f"File ID: {file_id}")
    
    # Try to get file info from database
    file_info = get_file_info_from_db(file_id)
    
    # Try different URL patterns
    urls_to_try = []
    
    if file_info and file_info.get('public_url'):
        urls_to_try.append(('Database Public URL', file_info['public_url']))
    
    # Proxy server endpoint
    proxy_url = f"{BASE_URL}/api/v1/tts/audio/{file_id}"
    urls_to_try.append(('Proxy Server', proxy_url))
    
    # R2 public URL (if we have r2_key)
    if file_info and file_info.get('r2_key'):
        r2_public_url = f"https://pub-06f0e98c01284240a79c03c4a59d4175.r2.dev/{file_info['r2_key']}"
        urls_to_try.append(('R2 Storage', r2_public_url))
    
    # Try each URL
    for url_name, url in urls_to_try:
        print(f"\n🔍 Trying {url_name}: {url}")
        try:
            response = requests.get(url, timeout=30, stream=True)
            if response.status_code == 200:
                print(f"✅ Successfully accessed via {url_name}")
                
                # Determine output filename
                if not output_path:
                    if file_info and file_info.get('original_filename'):
                        output_path = file_info['original_filename']
                    else:
                        output_path = f"{file_id}.wav"
                
                # Ensure output directory exists
                output_dir = os.path.dirname(output_path) if os.path.dirname(output_path) else '.'
                os.makedirs(output_dir, exist_ok=True)
                
                # Download file
                total_size = int(response.headers.get('content-length', 0))
                print(f"📥 Downloading to: {output_path}")
                print(f"   Size: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
                
                with open(output_path, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                print(f"\r   Progress: {percent:.1f}% ({downloaded:,}/{total_size:,} bytes)", end='', flush=True)
                
                print(f"\n✅ File downloaded successfully!")
                print(f"   Path: {os.path.abspath(output_path)}")
                print(f"   Size: {os.path.getsize(output_path):,} bytes")
                
                # Also print the URL for direct access
                print(f"\n🌐 Direct URL: {url}")
                print(f"   You can open this URL in your browser or audio player")
                
                return output_path
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue
    
    print(f"\n❌ Failed to download from all available sources")
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 download_audio.py <file_id|task_id> [output_path]")
        print("\nExamples:")
        print("  python3 download_audio.py 7ae4e379-2013-4608-8c84-588fbc01d381")
        print("  python3 download_audio.py 7e145dda-40bb-4cf3-a8c7-7db8ce99d277 output.wav")
        print("\nIf you provide a task_id, the script will extract the file_id from the task's miner responses")
        sys.exit(1)
    
    identifier = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Check if it's a task_id (UUID format) or file_id
    # Try to get file_id from task first
    file_id = get_audio_from_task(identifier)
    
    if not file_id:
        # Assume it's a file_id
        file_id = identifier
    
    if not file_id:
        print(f"❌ Could not find file_id for: {identifier}")
        sys.exit(1)
    
    print(f"📋 Using file_id: {file_id}")
    
    result = download_audio(file_id, output_path)
    
    if result:
        print(f"\n✅ Success! Audio file saved to: {result}")
    else:
        print(f"\n❌ Failed to download audio file")
        sys.exit(1)

if __name__ == "__main__":
    main()
