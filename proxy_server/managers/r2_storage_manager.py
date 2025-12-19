"""
Cloudflare R2 Storage Manager for Proxy Server
Handles file uploads, downloads, and storage operations using Cloudflare R2 (S3-compatible API)
"""

import uuid
import hashlib
import os
from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
from datetime import datetime
import mimetypes
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from database.postgresql_adapter import PostgreSQLAdapter

load_dotenv()

class R2StorageManager:
    def __init__(self, db, bucket_name: str = None, endpoint_url: str = None):
        """
        Initialize R2 Storage Manager
        
        Args:
            db: Database instance (PostgreSQL or Firestore)
            bucket_name: R2 bucket name (defaults to env var)
            endpoint_url: R2 S3 endpoint URL (defaults to env var)
        """
        self.db = db
        # PostgreSQL only - no Firestore support
        
        # Hardcoded R2 credentials
        self.access_key_id = "977bd81d90d2237a9ad26b6cb30b903b"
        self.secret_access_key = "198c70509cffba2cce1d763404fd6038a768353ebb65d4ec0964caa559669b1a"
        self.bucket_name = bucket_name or "llama-4b-ws-4-042"
        self.endpoint_url = endpoint_url or "https://3afa54a555b4e67eb6e376e3b5b6ab67.r2.cloudflarestorage.com"
        self.public_url = "https://pub-06f0e98c01284240a79c03c4a59d4175.r2.dev"
        
        print(f"✅ R2 credentials loaded (hardcoded)")
        print(f"   Access Key ID: {self.access_key_id[:20]}...")
        print(f"   Bucket: {self.bucket_name}")
        print(f"   Endpoint: {self.endpoint_url}")
        print(f"   Public URL: {self.public_url}")
        
        self.s3_client = None
        self.enabled = False
        
        # Initialize S3 client for R2
        try:
            if not self.access_key_id or not self.secret_access_key:
                print("⚠️  R2 credentials are missing")
                print("   File uploads will be disabled.")
                return
            
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name='auto'  # R2 uses 'auto' as region
            )
            
            # Test connection by checking if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                self.enabled = True
                print(f"✅ R2 Storage initialized successfully")
                print(f"   Bucket: {self.bucket_name}")
                print(f"   Endpoint: {self.endpoint_url}")
                print(f"   Public URL: {self.public_url}")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    print(f"⚠️  R2 bucket '{self.bucket_name}' not found")
                elif error_code == '403':
                    print(f"⚠️  Access denied to R2 bucket '{self.bucket_name}'")
                else:
                    print(f"⚠️  Error accessing R2 bucket: {e}")
                print("   File uploads will be disabled.")
                return
                
        except Exception as e:
            print(f"⚠️  Failed to initialize R2 Storage: {e}")
            print("   File uploads will be disabled.")
            return
        
        # File size limits
        self.max_file_size = 5 * 1024 * 1024 * 1024  # 5GB limit for R2
        
        if self.enabled:
            print(f"✅ R2 Storage ready")
            print(f"   Max file size: {self.max_file_size / (1024*1024*1024):.1f}GB")
    
    def _get_storage_path_for_type(self, file_type: str) -> str:
        """Get the appropriate storage path based on file type"""
        if file_type in ["transcription", "audio", "audio/wav", "audio/mp3", "audio/m4a"]:
            return "user_audio"
        elif file_type == "tts":
            return "tts_audio"
        elif file_type == "summarization":
            return "summarization_files"
        elif file_type in ["video_transcription", "video", "video/mp4", "video/avi", "video/mov"]:
            return "user_videos"
        elif file_type in ["document_translation", "text", "application/pdf", "text/plain"]:
            return "user_documents"
        else:
            return "temp"  # Default to temp for unknown types
    
    def _create_safe_filename(self, original_filename: str) -> str:
        """Create a safe filename for storage"""
        # Extract extension
        ext = Path(original_filename).suffix
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        safe_name = f"{unique_id}{ext}"
        return safe_name
    
    async def store_file(self, file_data: bytes, file_name: str, content_type: str = None, file_type: str = "audio") -> Dict[str, Any]:
        """
        Store a file in R2 and create metadata in Firestore
        
        Args:
            file_data: File content as bytes
            file_name: Original filename
            content_type: MIME type of the file
            file_type: Type of file (audio, video, document, etc.)
        
        Returns:
            Dictionary with file_id, file_name, file_size, storage_path, public_url, etc.
        """
        if not self.enabled:
            raise Exception("R2 Storage is not enabled. Check credentials and configuration.")
        
        # Validate file size
        file_size = len(file_data)
        if file_size > self.max_file_size:
            raise ValueError(f"File size ({file_size} bytes) exceeds maximum allowed size ({self.max_file_size} bytes)")
        
        # Generate file ID and safe filename
        file_id = str(uuid.uuid4())
        safe_filename = self._create_safe_filename(file_name)
        
        # Determine storage path
        storage_path = self._get_storage_path_for_type(file_type)
        r2_key = f"{storage_path}/{file_id}/{safe_filename}"
        
        # Detect content type if not provided
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_name)
            if not content_type:
                content_type = "application/octet-stream"
        
        try:
            # Upload to R2
            # Ensure metadata values are safe strings (S3 metadata must be strings)
            safe_original_filename = file_name
            if isinstance(file_name, bytes):
                try:
                    safe_original_filename = file_name.decode('utf-8', errors='replace')
                except:
                    safe_original_filename = "audio_file"
            elif not isinstance(file_name, str):
                safe_original_filename = str(file_name)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=r2_key,
                Body=file_data,
                ContentType=content_type,
                Metadata={
                    'original_filename': safe_original_filename[:255],  # S3 metadata limit
                    'file_id': file_id,
                    'file_type': file_type
                }
            )
            
            # Generate public URL (if bucket is configured for public access)
            public_url = f"{self.public_url}/{r2_key}"
            
            # Calculate file hash
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # Create metadata document in Firestore
            file_metadata = {
                'file_id': file_id,
                'original_filename': file_name,
                'safe_filename': safe_filename,
                'file_size': file_size,
                'content_type': content_type,
                'file_type': file_type,
                'storage_location': 'r2',
                'r2_bucket': self.bucket_name,
                'r2_key': r2_key,
                'public_url': public_url,
                'file_hash': file_hash,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            # Store metadata in PostgreSQL
            from database.postgresql_schema import File
            session = self.db._get_session()
            try:
                file_record = File(
                    file_id=file_id,
                    original_filename=file_metadata.get('original_filename', safe_filename),
                    safe_filename=safe_filename,
                    file_size=file_size,
                    content_type=content_type,
                    file_type=file_type,
                    storage_location='r2',
                    r2_bucket=self.bucket_name,
                    r2_key=r2_key,
                    public_url=public_url,
                    file_hash=file_metadata.get('file_hash', ''),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(file_record)
                session.commit()
            finally:
                session.close()
            
            print(f"✅ File stored in R2: {file_id}")
            print(f"   R2 Key: {r2_key}")
            print(f"   Size: {file_size} bytes")
            
            return file_metadata
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            raise Exception(f"Failed to upload file to R2: {error_code} - {error_message}")
        except Exception as e:
            raise Exception(f"Failed to store file: {str(e)}")
    
    async def retrieve_file(self, file_id: str) -> Optional[Tuple[bytes, str, str]]:
        """
        Retrieve a file from R2 using file_id
        
        Args:
            file_id: The file ID stored in Firestore
        
        Returns:
            Tuple of (file_content, content_type, original_filename) or None if not found
        """
        if not self.enabled:
            raise Exception("R2 Storage is not enabled. Check credentials and configuration.")
        
        try:
            # Get file metadata from PostgreSQL
            from database.postgresql_schema import File
            session = self.db._get_session()
            try:
                file_obj = session.query(File).filter(File.file_id == file_id).first()
                if not file_obj:
                    print(f"❌ File metadata not found: {file_id}")
                    return None
                file_metadata = {
                    'file_id': file_obj.file_id,
                    'r2_key': file_obj.r2_key,
                    'public_url': file_obj.public_url,
                    'original_filename': file_obj.original_filename,
                    'file_size': file_obj.file_size,
                    'content_type': file_obj.content_type
                }
            finally:
                session.close()
            
            if not file_metadata:
                return None
            
            r2_key = file_metadata.get('r2_key')
            
            if not r2_key:
                print(f"❌ R2 key not found in metadata for file: {file_id}")
                return None
            
            # Download from R2
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=r2_key
            )
            
            file_content = response['Body'].read()
            content_type = response.get('ContentType', file_metadata.get('content_type', 'application/octet-stream'))
            original_filename = file_metadata.get('original_filename', 'unknown')
            
            print(f"✅ File retrieved from R2: {file_id}")
            print(f"   Size: {len(file_content)} bytes")
            
            return (file_content, content_type, original_filename)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                print(f"❌ File not found in R2: {file_id}")
            else:
                print(f"❌ Error retrieving file from R2: {e}")
            return None
        except Exception as e:
            print(f"❌ Failed to retrieve file: {str(e)}")
            return None
    
    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from R2 and remove metadata from Firestore
        
        Args:
            file_id: The file ID to delete
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            raise Exception("R2 Storage is not enabled.")
        
        try:
            # Get file metadata from PostgreSQL
            from database.postgresql_schema import File
            session = self.db._get_session()
            try:
                file_obj = session.query(File).filter(File.file_id == file_id).first()
                if not file_obj:
                    print(f"⚠️  File metadata not found: {file_id}")
                    return False
                
                r2_key = file_obj.r2_key
                
                if r2_key:
                    # Delete from R2
                    try:
                        self.s3_client.delete_object(
                            Bucket=self.bucket_name,
                            Key=r2_key
                        )
                        print(f"✅ File deleted from R2: {r2_key}")
                    except ClientError as e:
                        print(f"⚠️  Error deleting file from R2: {e}")
                
                # Delete metadata from PostgreSQL
                session.delete(file_obj)
                session.commit()
                print(f"✅ File metadata deleted: {file_id}")
                
                return True
            finally:
                session.close()
            
        except Exception as e:
            print(f"❌ Failed to delete file: {str(e)}")
            return False
    
    def get_file_url(self, file_id: str) -> Optional[str]:
        """
        Get the public URL for a file
        
        Args:
            file_id: The file ID
        
        Returns:
            Public URL or None if not found
        """
        try:
            # PostgreSQL: Get file public URL
            from database.postgresql_schema import File
            session = self.db._get_session()
            try:
                file_obj = session.query(File).filter(File.file_id == file_id).first()
                if file_obj:
                    return file_obj.public_url
                return None
            finally:
                session.close()
        except Exception as e:
            print(f"❌ Failed to get file URL: {str(e)}")
            return None

