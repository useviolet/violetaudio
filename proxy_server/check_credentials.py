#!/usr/bin/env python3
"""
Check which credentials file is being used for database operations
"""

import os
import sys
from pathlib import Path

# Add proxy_server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_credentials():
    """Check which credentials file is being used"""
    print("=" * 70)
    print("🔍 Checking Database Credentials Configuration")
    print("=" * 70)
    
    # Check the paths that main.py uses
    possible_paths = [
        "db/violet-rename.json",
        "db/violet.json",
        os.path.join(os.path.dirname(__file__), "db", "violet-rename.json"),
        os.path.join(os.path.dirname(__file__), "db", "violet.json")
    ]
    
    print("\n📂 Checking credential file paths (in order of priority):")
    credentials_path = None
    
    for i, path in enumerate(possible_paths, 1):
        abs_path = os.path.abspath(path) if not os.path.isabs(path) else path
        exists = os.path.exists(abs_path)
        status = "✅ EXISTS" if exists else "❌ NOT FOUND"
        print(f"   {i}. {abs_path}")
        print(f"      {status}")
        
        if exists and credentials_path is None:
            credentials_path = abs_path
    
    if credentials_path:
        print(f"\n✅ Credentials file being used: {credentials_path}")
        
        # Get file info
        file_size = os.path.getsize(credentials_path)
        print(f"   File size: {file_size} bytes")
        
        # Read and show project ID
        try:
            import json
            with open(credentials_path, 'r') as f:
                creds = json.load(f)
            print(f"   Project ID: {creds.get('project_id', 'N/A')}")
            print(f"   Client Email: {creds.get('client_email', 'N/A')[:50]}...")
        except Exception as e:
            print(f"   ⚠️  Error reading credentials: {e}")
    else:
        print(f"\n❌ No credentials file found!")
        print(f"   The proxy server will fail to start without credentials.")
    
    # Check if DatabaseManager would use this
    print(f"\n🔍 Testing DatabaseManager initialization...")
    try:
        from database.schema import DatabaseManager
        
        if credentials_path:
            db_manager = DatabaseManager(credentials_path)
            print(f"✅ DatabaseManager can be initialized with: {credentials_path}")
            
            # Try to initialize (but don't actually connect)
            print(f"   Note: Full initialization requires Firebase connection")
        else:
            print(f"❌ Cannot initialize DatabaseManager - no credentials found")
    except Exception as e:
        print(f"⚠️  Error testing DatabaseManager: {e}")
    
    # Check for other credential files
    print(f"\n📂 Checking for other credential files in db/ directory:")
    db_dir = Path(__file__).parent / "db"
    if db_dir.exists():
        for cred_file in db_dir.glob("*.json"):
            print(f"   - {cred_file.name} ({cred_file.stat().st_size} bytes)")
    else:
        print(f"   ⚠️  db/ directory not found")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_credentials()

