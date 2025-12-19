"""
File Manager for Enhanced Proxy Server
Handles file uploads, downloads, and storage operations using Firebase Cloud Storage ONLY
"""

import uuid
import hashlib
import os
import shutil
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import mimetypes
from datetime import datetime

class FileManager:
    def __init__(self, db):
        self.db = db
        # PostgreSQL only
        
        # Import and initialize R2 Storage manager (replacing Firebase Cloud Storage)
        try:
            from .r2_storage_manager import R2StorageManager
            self.r2_storage_manager = R2StorageManager(db)
            if self.r2_storage_manager.enabled:
                print("✅ R2 Storage manager initialized")
            else:
                print("⚠️  R2 Storage manager initialized but disabled (no credentials)")
        except ImportError as e:
            print(f"⚠️  R2 Storage manager import failed: {e}")
            print("   Install boto3: pip install boto3")
            self.r2_storage_manager = None
        except Exception as e:
            print(f"⚠️  R2 Storage manager initialization failed: {e}")
            # Don't raise - allow server to start without R2 for local testing
            self.r2_storage_manager = None
        
        # Keep Firebase Storage Manager for backward compatibility (if needed)
        self.firebase_storage_manager = None
    
    async def upload_file(self, file_data: bytes, file_name: str, content_type: str, file_type: str = "audio") -> str:
        """Upload file using R2 Storage"""
        try:
            if not self.r2_storage_manager or not self.r2_storage_manager.enabled:
                raise Exception("R2 Storage is not enabled. Check R2 credentials in .env file.")
            
            # Use R2 Storage
            file_metadata = await self.r2_storage_manager.store_file(file_data, file_name, content_type, file_type)
            file_id = file_metadata['file_id']
            print(f"✅ File uploaded using R2 Storage: {file_id}")
            return file_id
            
        except Exception as e:
            print(f"❌ Failed to upload file {file_name}: {e}")
            raise
    
    async def download_file(self, file_id: str) -> Optional[bytes]:
        """Download file from R2 Storage, or return None if not available (caller can use public URL)"""
        try:
            if not self.r2_storage_manager or not self.r2_storage_manager.enabled:
                # R2 not enabled - return None so caller can use public URL
                print(f"⚠️  R2 Storage not enabled for file {file_id}, will use public URL if available")
                return None
            
            # Use R2 Storage
            result = await self.r2_storage_manager.retrieve_file(file_id)
            if result:
                file_content, content_type, file_name = result
                print(f"✅ File downloaded from R2 Storage: {file_name}")
                return file_content
            else:
                print(f"❌ File {file_id} not found in R2 Storage")
                return None
            
        except Exception as e:
            print(f"⚠️  Failed to download file {file_id} from R2: {e}")
            # Return None so caller can fall back to public URL
            return None
    
    async def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Get file metadata from R2 Storage"""
        try:
            # PostgreSQL: Get from database
            from database.postgresql_schema import File
            session = self.db._get_session()
            try:
                file = session.query(File).filter(File.file_id == file_id).first()
                if file:
                    file_info = {
                        'file_id': file.file_id,
                        'original_filename': file.original_filename,
                        'safe_filename': file.safe_filename,
                        'file_size': file.file_size,
                        'content_type': file.content_type,
                        'file_type': file.file_type,
                        'storage_location': file.storage_location,
                        'r2_bucket': file.r2_bucket,
                        'r2_key': file.r2_key,
                        'public_url': file.public_url,
                        'file_hash': file.file_hash,
                        'created_at': file.created_at,
                        'updated_at': file.updated_at
                    }
                    print(f"✅ File metadata retrieved from PostgreSQL: {file_id}")
                    return file_info
                else:
                    print(f"❌ File {file_id} not found in PostgreSQL")
                    return None
            finally:
                session.close()
                
        except Exception as e:
            print(f"❌ Failed to get file metadata {file_id}: {e}")
            return None
    
    async def delete_file(self, file_id: str) -> bool:
        """Delete file from R2 Storage"""
        try:
            if not self.r2_storage_manager or not self.r2_storage_manager.enabled:
                raise Exception("R2 Storage is not enabled.")
            
            # Use R2 Storage
            result = await self.r2_storage_manager.delete_file(file_id)
            if result:
                print(f"✅ File {file_id} deleted from R2 Storage")
            else:
                print(f"❌ Failed to delete file {file_id} from R2 Storage")
            return result
            
        except Exception as e:
            print(f"❌ Failed to delete file {file_id}: {e}")
            return False
    
    async def cleanup_expired_files(self, max_age_hours: int = 24):
        """Clean up expired files to save storage space"""
        try:
            from datetime import datetime, timedelta
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            # PostgreSQL: Query expired files
            from database.postgresql_schema import File
            session = self.db._get_session()
            try:
                expired_files = session.query(File).filter(File.created_at < cutoff_time).all()
                deleted_count = 0
                for file in expired_files:
                    if await self.delete_file(file.file_id):
                        deleted_count += 1
                if deleted_count > 0:
                    print(f"🧹 Cleaned up {deleted_count} expired files")
            finally:
                session.close()
                
                deleted_count = 0
                for doc in expired_files:
                    file_data = doc.to_dict()
                    if await self.delete_file(file_data['file_id']):
                        deleted_count += 1
                
                if deleted_count > 0:
                    print(f"🧹 Cleaned up {deleted_count} expired files")
                
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
    
    async def list_files_by_type(self, file_type: str) -> List[Dict]:
        """List all files of a specific type"""
        try:
            # PostgreSQL: Query files by type
            from database.postgresql_schema import File
            session = self.db._get_session()
            try:
                files = session.query(File).filter(File.file_type == file_type).all()
                file_list = []
                for file in files:
                    file_list.append({
                        'file_id': file.file_id,
                        'original_filename': file.original_filename,
                        'file_size': file.file_size,
                        'content_type': file.content_type,
                        'public_url': file.public_url,
                        'created_at': file.created_at
                    })
                return file_list
            finally:
                session.close()
            
        except Exception as e:
            print(f"❌ Error listing files by type: {e}")
            return []
    
    async def get_storage_statistics(self) -> Dict:
        """Get storage statistics from R2 Storage"""
        try:
            # PostgreSQL: Count files
            from database.postgresql_schema import File
            session = self.db._get_session()
            try:
                total_files = session.query(File).count()
                files = session.query(File).all()
                total_size = sum(f.file_size or 0 for f in files)
                
                return {
                    'total_files': total_files,
                    'total_size_bytes': total_size,
                    'total_size_mb': total_size / (1024 * 1024),
                    'storage_type': 'R2'
                }
            finally:
                session.close()
                
        except Exception as e:
            return {'error': str(e)}
    
    def get_file_url(self, file_id: str) -> Optional[str]:
        """Get public URL for a file from R2"""
        try:
            if self.r2_storage_manager and self.r2_storage_manager.enabled:
                return self.r2_storage_manager.get_file_url(file_id)
            else:
                # Get from database (PostgreSQL)
                from database.postgresql_schema import File
                session = self.db._get_session()
                try:
                    file = session.query(File).filter(File.file_id == file_id).first()
                    return file.public_url if file else None
                finally:
                    session.close()
        except Exception as e:
            print(f"❌ Error getting file URL: {e}")
            return None
    
    async def file_exists(self, file_id: str) -> bool:
        """Check if file exists in R2 Storage"""
        try:
            file_info = await self.get_file_metadata(file_id)
            return file_info is not None
        except Exception as e:
            print(f"❌ Error checking file existence: {e}")
            return False
