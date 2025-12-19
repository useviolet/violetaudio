"""
Verify R2 credentials are hardcoded and working
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from managers.r2_storage_manager import R2StorageManager
import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase():
    """Initialize Firebase"""
    cred_path = Path(__file__).parent / "db" / "violet.json"
    if not cred_path.exists():
        print(f"❌ Firebase credentials not found at {cred_path}")
        return None
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(str(cred_path))
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

def main():
    print("="*70)
    print("🔍 Verifying R2 Credentials (Hardcoded)")
    print("="*70)
    
    # Initialize Firebase
    print("\n📦 Initializing Firebase...")
    db = init_firebase()
    if not db:
        return False
    
    # Initialize R2 Storage Manager
    print("\n🔧 Initializing R2 Storage Manager...")
    try:
        r2_manager = R2StorageManager(db)
        
        print("\n📋 Credentials Summary:")
        print(f"   Access Key ID: {r2_manager.access_key_id[:20]}...")
        print(f"   Secret Key: {'*' * 20}...{r2_manager.secret_access_key[-4:]}")
        print(f"   Bucket: {r2_manager.bucket_name}")
        print(f"   Endpoint: {r2_manager.endpoint_url}")
        print(f"   Public URL: {r2_manager.public_url}")
        
        if r2_manager.enabled:
            print("\n✅ R2 Storage is ENABLED and ready!")
            
            # Test upload
            print("\n🧪 Testing R2 connection with a small test file...")
            test_data = b"Hello, R2! This is a test file."
            try:
                import asyncio
                result = asyncio.run(r2_manager.store_file(
                    test_data,
                    "test_file.txt",
                    "text/plain",
                    "audio"
                ))
                print(f"✅ Test upload successful!")
                print(f"   File ID: {result['file_id']}")
                print(f"   Public URL: {result['public_url']}")
                
                # Clean up
                asyncio.run(r2_manager.delete_file(result['file_id']))
                print(f"✅ Test file cleaned up")
                
                return True
            except Exception as e:
                print(f"❌ Test upload failed: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print("\n❌ R2 Storage is DISABLED")
            return False
            
    except Exception as e:
        print(f"\n❌ Failed to initialize R2 Storage Manager: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

