#!/usr/bin/env python3
"""
Upload speaker audio file to R2 bucket in TTS speaker wavs folder
"""

import sys
import os
from pathlib import Path

# Add proxy_server to path
proxy_server_path = Path(__file__).parent
sys.path.insert(0, str(proxy_server_path))

from managers.r2_storage_manager import R2StorageManager
from database.schema import DatabaseManager

def upload_speaker_audio():
    """Upload speaker audio to R2 bucket"""
    print("="*80)
    print("🎤 Uploading Speaker Audio to R2 Bucket")
    print("="*80)
    
    # Initialize Firebase
    credentials_path = "/Users/user/Documents/Jarvis/violet/proxy_server/db/violet.json"
    if not os.path.exists(credentials_path):
        credentials_path = os.path.join(proxy_server_path, "db", "violet.json")
    
    if not os.path.exists(credentials_path):
        print(f"❌ Firebase credentials not found at {credentials_path}")
        return
    
    db_manager = DatabaseManager(credentials_path)
    db_manager.initialize()
    db = db_manager.get_db()
    
    # Initialize R2 Storage Manager (requires db)
    r2_manager = R2StorageManager(db)
    
    # Audio file path
    audio_file_path = "/Users/user/Documents/Jarvis/violet/LJ037-0171.wav"
    voice_name = "english_alice"
    
    if not os.path.exists(audio_file_path):
        print(f"❌ Audio file not found: {audio_file_path}")
        return
    
    print(f"\n📁 Reading audio file: {audio_file_path}")
    with open(audio_file_path, 'rb') as f:
        audio_data = f.read()
    
    print(f"   File size: {len(audio_data)} bytes ({len(audio_data)/1024:.2f} KB)")
    
    # Create folder path: TTS speaker wavs/english_alice.wav
    folder_path = "TTS speaker wavs"
    file_name = f"{voice_name}.wav"
    r2_key = f"{folder_path}/{file_name}"
    
    print(f"\n📤 Uploading to R2 bucket...")
    print(f"   R2 Key: {r2_key}")
    
    try:
        # Upload to R2 - manually construct R2 key with folder path
        r2_key = f"{folder_path}/{file_name}"
        
        # Use boto3 directly to upload to specific folder
        import boto3
        s3_client = boto3.client(
            's3',
            endpoint_url=r2_manager.endpoint_url,
            aws_access_key_id=r2_manager.access_key_id,
            aws_secret_access_key=r2_manager.secret_access_key,
            region_name='auto'
        )
        
        # Upload file
        s3_client.put_object(
            Bucket=r2_manager.bucket_name,
            Key=r2_key,
            Body=audio_data,
            ContentType="audio/wav"
        )
        
        # Create public URL
        public_url = f"{r2_manager.public_url}/{r2_key}"
        
        # Create file metadata
        file_id = str(uuid.uuid4())
        file_metadata = {
            'file_id': file_id,
            'file_name': file_name,
            'file_size': len(audio_data),
            'file_type': 'audio/wav',
            'r2_key': r2_key,
            'public_url': public_url,
            'storage_location': 'r2',
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        # Store metadata in Firestore
        r2_manager.files_collection.document(file_id).set(file_metadata)
        
        print(f"\n✅ Successfully uploaded speaker audio!")
        print(f"   File ID: {file_metadata.get('file_id')}")
        print(f"   Public URL: {file_metadata.get('public_url')}")
        print(f"   R2 Key: {file_metadata.get('r2_key')}")
        
        # Store voice mapping in database
        print(f"\n💾 Storing voice mapping in database...")
        voice_data = {
            'voice_name': voice_name,
            'display_name': 'English Alice',
            'language': 'en',
            'file_id': file_metadata.get('file_id'),
            'r2_key': file_metadata.get('r2_key'),
            'public_url': file_metadata.get('public_url'),
            'file_name': file_name,
            'file_size': len(audio_data),
            'file_type': 'audio/wav',
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        voices_ref = db.collection('voices').document(voice_name)
        voices_ref.set(voice_data)
        
        print(f"✅ Voice mapping stored in database!")
        print(f"   Voice name: {voice_name}")
        print(f"   Display name: {voice_data['display_name']}")
        print(f"   Language: {voice_data['language']}")
        
        return file_metadata
        
    except Exception as e:
        print(f"❌ Error uploading speaker audio: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    import uuid
    from datetime import datetime
    from firebase_admin import firestore
    upload_speaker_audio()

