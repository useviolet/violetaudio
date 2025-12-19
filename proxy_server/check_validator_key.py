#!/usr/bin/env python3
"""
Check if validator API key exists in database and .env file
"""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

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

def check_env_file():
    """Check if VALIDATOR_API_KEY exists in .env file"""
    print("="*80)
    print("🔍 Checking .env file for VALIDATOR_API_KEY...")
    print("="*80)
    
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        print(f"❌ .env file not found at {env_file}")
        return None
    
    load_dotenv(env_file)
    validator_key = os.getenv('VALIDATOR_API_KEY')
    
    if validator_key:
        print(f"✅ VALIDATOR_API_KEY found in .env file")
        print(f"   Key: {validator_key[:20]}...{validator_key[-10:]}")
        print(f"   Length: {len(validator_key)}")
        return validator_key
    else:
        print(f"❌ VALIDATOR_API_KEY not found in .env file")
        return None

def find_validator_users(db):
    """Find users with validator role"""
    print("\n" + "="*80)
    print("🔍 Searching for validator users in database...")
    print("="*80)
    
    try:
        users_ref = db.collection('users')
        query = users_ref.where('role', '==', 'validator').stream()
        
        validators = []
        for user in query:
            user_data = user.to_dict()
            validators.append({
                'user_id': user.id,
                'email': user_data.get('email', 'N/A'),
                'api_key': user_data.get('api_key'),
                'hotkey': user_data.get('hotkey', 'N/A'),
                'uid': user_data.get('uid', 'N/A'),
                'network': user_data.get('network', 'N/A')
            })
        
        if validators:
            print(f"✅ Found {len(validators)} validator user(s):")
            for i, v in enumerate(validators, 1):
                print(f"\n   Validator {i}:")
                print(f"      User ID: {v['user_id']}")
                print(f"      Email: {v['email']}")
                print(f"      API Key: {v['api_key'][:20]}...{v['api_key'][-10:] if v['api_key'] else 'N/A'}")
                print(f"      Hotkey: {v['hotkey']}")
                print(f"      UID: {v['uid']}")
                print(f"      Network: {v['network']}")
            return validators
        else:
            print("❌ No validator users found in database")
            return []
            
    except Exception as e:
        print(f"❌ Error searching for validators: {e}")
        import traceback
        traceback.print_exc()
        return []

def update_env_file(api_key):
    """Update .env file with VALIDATOR_API_KEY"""
    print("\n" + "="*80)
    print("📝 Updating .env file with VALIDATOR_API_KEY...")
    print("="*80)
    
    env_file = Path(__file__).parent.parent / ".env"
    
    if not env_file.exists():
        print(f"❌ .env file not found at {env_file}")
        return False
    
    try:
        # Read current .env file
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Check if VALIDATOR_API_KEY already exists
        key_found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith('VALIDATOR_API_KEY='):
                key_found = True
                new_lines.append(f'VALIDATOR_API_KEY={api_key}\n')
            else:
                new_lines.append(line)
        
        # If not found, append it
        if not key_found:
            new_lines.append(f'\n# Validator API Key\nVALIDATOR_API_KEY={api_key}\n')
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(new_lines)
        
        print(f"✅ Updated .env file with VALIDATOR_API_KEY")
        print(f"   Key: {api_key[:20]}...{api_key[-10:]}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # Initialize Firebase
    db = init_firebase()
    if not db:
        return False
    
    # Check .env file
    env_key = check_env_file()
    
    # Find validator users
    validators = find_validator_users(db)
    
    if not validators:
        print("\n" + "="*80)
        print("⚠️  No validator users found in database")
        print("="*80)
        print("   To create a validator user:")
        print("   1. Register as a client first")
        print("   2. Use /api/v1/auth/generate-api-key endpoint with validator credentials")
        return False
    
    # Get first validator's API key
    validator = validators[0]
    db_key = validator.get('api_key')
    
    if not db_key:
        print("\n❌ Validator user has no API key")
        return False
    
    # Compare with .env file
    if env_key:
        if env_key == db_key:
            print("\n✅ VALIDATOR_API_KEY in .env matches database")
            return True
        else:
            print("\n⚠️  VALIDATOR_API_KEY in .env does NOT match database")
            print("   Updating .env file with database key...")
            return update_env_file(db_key)
    else:
        print("\n⚠️  VALIDATOR_API_KEY not in .env file")
        print("   Adding it now...")
        return update_env_file(db_key)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

