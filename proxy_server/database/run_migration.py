#!/usr/bin/env python3
"""
Run complete migration from Firestore to PostgreSQL
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from proxy_server.database.schema import DatabaseManager
from proxy_server.database.postgresql_adapter import PostgreSQLAdapter
from proxy_server.database.postgresql_schema import (
    Base, Task, File, TextContent, Miner, MinerStatus, User, Voice, SystemMetrics
)
from firebase_admin import firestore
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

def migrate_collection(session: Session, firestore_db, collection_name: str, model_class, transform_func=None):
    """Migrate a Firestore collection to PostgreSQL"""
    print(f"\n📦 Migrating {collection_name}...")
    
    try:
        collection_ref = firestore_db.collection(collection_name)
        docs = collection_ref.stream()
        
        migrated = 0
        errors = 0
        
        for doc in docs:
            try:
                data = doc.to_dict()
                
                # Use document ID if no ID field in data
                if hasattr(model_class, '__table__'):
                    pk_col = list(model_class.__table__.primary_key.columns)[0]
                    pk_name = pk_col.name
                    
                    # Set primary key from document ID or data
                    if pk_name not in data:
                        if pk_name == 'task_id' or pk_name.endswith('_id'):
                            data[pk_name] = doc.id
                        elif pk_name == 'uid':
                            data[pk_name] = int(doc.id) if doc.id.isdigit() else doc.id
                        elif pk_name == 'voice_name':
                            data[pk_name] = doc.id
                        else:
                            data[pk_name] = doc.id
                
                # Transform data if function provided
                if transform_func:
                    data = transform_func(data, doc.id)
                
                # Convert timestamps
                for key, value in data.items():
                    if isinstance(value, (firestore.Timestamp, datetime)):
                        if hasattr(value, 'timestamp'):
                            data[key] = datetime.fromtimestamp(value.timestamp())
                        elif isinstance(value, datetime):
                            pass  # Already datetime
                
                # Create model instance
                instance = model_class(**{k: v for k, v in data.items() if hasattr(model_class, k)})
                session.add(instance)
                
                migrated += 1
                
                if migrated % 100 == 0:
                    print(f"   📊 Migrated {migrated} records...")
                    session.commit()  # Commit in batches
                    
            except Exception as e:
                errors += 1
                print(f"   ⚠️ Error migrating {doc.id}: {e}")
                if errors > 10:
                    print(f"   ⚠️ Too many errors, skipping {collection_name}")
                    break
        
        session.commit()
        print(f"   ✅ Migrated {migrated} {collection_name} records ({errors} errors)")
        return migrated, errors
        
    except Exception as e:
        session.rollback()
        print(f"   ❌ Error migrating {collection_name}: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

def transform_task_data(data: dict, doc_id: str) -> dict:
    """Transform task data for PostgreSQL"""
    # Convert status, priority, task_type to enum values
    if 'status' in data and isinstance(data['status'], str):
        data['status'] = data['status']  # Will be converted by SQLAlchemy
    if 'priority' in data and isinstance(data['priority'], str):
        data['priority'] = data['priority']
    if 'task_type' in data and isinstance(data['task_type'], str):
        data['task_type'] = data['task_type']
    
    # Handle assigned_miners array
    if 'assigned_miners' in data and not isinstance(data['assigned_miners'], list):
        data['assigned_miners'] = []
    
    # Handle input_file reference
    if 'input_file' in data and isinstance(data['input_file'], dict):
        file_id = data['input_file'].get('file_id')
        if file_id:
            data['input_file_id'] = file_id
        del data['input_file']
    
    # Handle input_text reference
    if 'input_text' in data:
        if isinstance(data['input_text'], dict):
            content_id = data['input_text'].get('content_id')
            if content_id:
                data['input_text_id'] = content_id
        del data['input_text']
    
    return data

def main():
    """Main migration function"""
    print("="*80)
    print("🚀 Starting Data Migration: Firestore → PostgreSQL")
    print("="*80)
    
    # Initialize Firestore
    credentials_path = "/Users/user/Documents/Jarvis/violet/proxy_server/db/violet.json"
    if not os.path.exists(credentials_path):
        print(f"❌ Firebase credentials not found at {credentials_path}")
        return False
    
    print("\n1️⃣ Initializing Firestore...")
    db_manager = DatabaseManager(credentials_path)
    db_manager.initialize()
    firestore_db = db_manager.get_db()
    print("   ✅ Firestore connected")
    
    # Initialize PostgreSQL
    print("\n2️⃣ Initializing PostgreSQL...")
    database_url = 'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    postgresql = PostgreSQLAdapter(database_url)
    print("   ✅ PostgreSQL connected")
    
    # Get session
    session = postgresql._get_session()
    
    stats = {}
    
    try:
        # Migrate in dependency order
        print("\n3️⃣ Starting data migration...")
        
        # Users first (no dependencies)
        stats['users'] = migrate_collection(session, firestore_db, 'users', User)
        
        # Files (no dependencies)
        stats['files'] = migrate_collection(session, firestore_db, 'files', File)
        
        # Text content (no dependencies)
        stats['text_content'] = migrate_collection(session, firestore_db, 'text_content', TextContent)
        
        # Voices (depends on files)
        stats['voices'] = migrate_collection(session, firestore_db, 'voices', Voice)
        
        # Miners (no dependencies)
        stats['miners'] = migrate_collection(session, firestore_db, 'miners', Miner)
        
        # Miner status (depends on miners)
        stats['miner_status'] = migrate_collection(session, firestore_db, 'miner_status', MinerStatus)
        
        # Tasks (depends on files, text_content, users)
        stats['tasks'] = migrate_collection(session, firestore_db, 'tasks', Task, transform_task_data)
        
        # Print summary
        print("\n" + "="*80)
        print("📊 Migration Summary")
        print("="*80)
        
        total_migrated = 0
        total_errors = 0
        
        for collection, (migrated, errors) in stats.items():
            status = "✅" if errors == 0 else "⚠️"
            print(f"{status} {collection}: {migrated} migrated, {errors} errors")
            total_migrated += migrated
            total_errors += errors
        
        print(f"\n📈 Total: {total_migrated} records migrated, {total_errors} errors")
        print("="*80)
        
        if total_errors == 0:
            print("\n🎉 Migration completed successfully!")
            return True
        else:
            print(f"\n⚠️ Migration completed with {total_errors} errors")
            return False
            
    except Exception as e:
        session.rollback()
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


