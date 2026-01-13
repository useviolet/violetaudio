#!/usr/bin/env python3
"""
Script to find a file and get its public URL
"""

import sys
import os
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

def get_database_url():
    """Get database URL from environment or use default"""
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

def find_file_by_name(filename: str):
    """Find file in database by filename and return public URL"""
    print(f"\n🔍 Searching for file: {filename}")
    
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
            # Search in files table by filename
            query = text("""
                SELECT 
                    file_id,
                    original_filename,
                    safe_filename,
                    public_url,
                    r2_key,
                    storage_location,
                    file_size,
                    created_at
                FROM files
                WHERE original_filename = :filename 
                   OR safe_filename = :filename
                   OR r2_key LIKE :pattern
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            # Try exact match and pattern match
            result = conn.execute(query, {
                'filename': filename,
                'pattern': f'%{filename}%'
            })
            
            files = result.fetchall()
            
            if files:
                print(f"\n✅ Found {len(files)} file(s) matching '{filename}':\n")
                for file in files:
                    (file_id, original_filename, safe_filename, public_url, 
                     r2_key, storage_location, file_size, created_at) = file
                    
                    print(f"📄 File ID: {file_id}")
                    print(f"   Original Filename: {original_filename}")
                    print(f"   Safe Filename: {safe_filename}")
                    print(f"   Storage: {storage_location}")
                    print(f"   Size: {file_size:,} bytes" if file_size else "   Size: Unknown")
                    print(f"   Created: {created_at}")
                    if r2_key:
                        print(f"   R2 Key: {r2_key}")
                    if public_url:
                        print(f"   🌐 Public URL: {public_url}")
                        print(f"\n✅ Direct Link: {public_url}\n")
                    else:
                        print(f"   ⚠️  No public URL found")
                        # Try to construct R2 URL if we have r2_key
                        if r2_key and storage_location == 'r2':
                            # R2 public URLs typically follow this pattern
                            # We need to check what the R2 public domain is
                            print(f"   💡 File is in R2 storage but no public_url in database")
                            print(f"   💡 R2 Key: {r2_key}")
                
                # Return the first file's public URL if available
                if files[0][3]:  # public_url is at index 3
                    return files[0][3]
                elif files[0][4] and files[0][5] == 'r2':  # r2_key and storage_location
                    print(f"\n⚠️  No public_url in database, but file exists in R2")
                    print(f"   R2 Key: {files[0][4]}")
                    return None
            else:
                print(f"\n❌ No file found in database matching '{filename}'")
                
                # Check miner_responses in tasks table
                print(f"\n🔍 Checking miner responses in tasks table...")
                task_query = text("""
                    SELECT 
                        task_id,
                        miner_responses,
                        best_response
                    FROM tasks
                    WHERE miner_responses::text LIKE :pattern
                       OR best_response::text LIKE :pattern
                """)
                
                task_result = conn.execute(task_query, {'pattern': f'%{filename}%'})
                tasks = task_result.fetchall()
                
                if tasks:
                    print(f"✅ Found {len(tasks)} task(s) with references to this file:\n")
                    for task in tasks:
                        task_id, miner_responses, best_response = task
                        print(f"📋 Task ID: {task_id}")
                        if miner_responses:
                            print(f"   Miner Responses: {json.dumps(miner_responses, indent=2)}")
                        if best_response:
                            print(f"   Best Response: {json.dumps(best_response, indent=2)}")
                            
                            # Try to extract file_id or URL from best_response
                            if isinstance(best_response, dict):
                                output_data = best_response.get('output_data', {})
                                audio_file = output_data.get('audio_file', {})
                                file_id = audio_file.get('file_id')
                                file_url = audio_file.get('public_url')
                                
                                if file_url:
                                    print(f"\n✅ Found URL in best_response: {file_url}")
                                    return file_url
                                elif file_id:
                                    print(f"\n💡 Found file_id in best_response: {file_id}")
                                    # Query files table with this file_id
                                    file_query = text("""
                                        SELECT public_url, r2_key, storage_location
                                        FROM files
                                        WHERE file_id = :file_id
                                    """)
                                    file_result = conn.execute(file_query, {'file_id': file_id})
                                    file_row = file_result.fetchone()
                                    if file_row:
                                        public_url, r2_key, storage_location = file_row
                                        if public_url:
                                            print(f"✅ Public URL: {public_url}")
                                            return public_url
                
                # Check local storage
                print(f"\n🔍 Checking local storage...")
                local_paths = [
                    f"proxy_server/local_storage/tts_audio/{filename}",
                    f"local_storage/tts_audio/{filename}",
                    f"tts_audio/{filename}",
                    filename
                ]
                
                for local_path in local_paths:
                    full_path = os.path.join(_project_root, local_path)
                    if os.path.exists(full_path):
                        print(f"✅ Found file locally: {full_path}")
                        print(f"   File size: {os.path.getsize(full_path):,} bytes")
                        print(f"\n⚠️  File is stored locally, not uploaded to R2 yet")
                        print(f"   Local path: {full_path}")
                        return None
                
                print(f"❌ File not found in local storage either")
                return None
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error searching for file: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "0c27a7cb-f23e-41cb-8b18-72f180dd26f6_6_d04fb965.wav"
    
    print("=" * 80)
    print("  File URL Finder")
    print("=" * 80)
    
    url = find_file_by_name(filename)
    
    if url:
        print("\n" + "=" * 80)
        print("✅ FINAL RESULT:")
        print("=" * 80)
        print(f"🌐 Public URL: {url}")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("⚠️  No public URL found")
        print("=" * 80)
        print("The file may be:")
        print("  1. Still being processed/uploaded")
        print("  2. Stored locally (not yet uploaded to R2)")
        print("  3. Not yet created")
        print("=" * 80)

if __name__ == "__main__":
    main()
