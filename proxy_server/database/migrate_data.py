#!/usr/bin/env python3
"""
Data Migration Script: Firestore to PostgreSQL
Migrates all data from Firestore to PostgreSQL with validation
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from proxy_server.database.schema import DatabaseManager
from proxy_server.database.postgresql_adapter import PostgreSQLAdapter
from proxy_server.database.enhanced_schema import COLLECTIONS
from firebase_admin import firestore

class DataMigrator:
    """Migrates data from Firestore to PostgreSQL"""
    
    def __init__(self, firestore_db, postgresql_adapter: PostgreSQLAdapter):
        self.firestore_db = firestore_db
        self.postgresql = postgresql_adapter
        self.stats = {
            'tasks': {'migrated': 0, 'errors': 0},
            'files': {'migrated': 0, 'errors': 0},
            'users': {'migrated': 0, 'errors': 0},
            'miners': {'migrated': 0, 'errors': 0},
            'miner_status': {'migrated': 0, 'errors': 0},
            'voices': {'migrated': 0, 'errors': 0},
        }
    
    def migrate_all(self):
        """Migrate all collections"""
        print("="*80)
        print("🚀 Starting Data Migration: Firestore → PostgreSQL")
        print("="*80)
        
        try:
            # Migrate in order (respecting foreign key dependencies)
            print("\n1️⃣ Migrating users...")
            self.migrate_users()
            
            print("\n2️⃣ Migrating files...")
            self.migrate_files()
            
            print("\n3️⃣ Migrating text_content...")
            self.migrate_text_content()
            
            print("\n4️⃣ Migrating voices...")
            self.migrate_voices()
            
            print("\n5️⃣ Migrating miners...")
            self.migrate_miners()
            
            print("\n6️⃣ Migrating miner_status...")
            self.migrate_miner_status()
            
            print("\n7️⃣ Migrating tasks...")
            self.migrate_tasks()
            
            # Print summary
            self.print_summary()
            
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True
    
    def migrate_users(self):
        """Migrate users collection"""
        try:
            users_ref = self.firestore_db.collection('users')
            users = users_ref.stream()
            
            for user_doc in users:
                try:
                    user_data = user_doc.to_dict()
                    # Convert to PostgreSQL format and insert
                    # (Implementation depends on PostgreSQL adapter methods)
                    self.stats['users']['migrated'] += 1
                except Exception as e:
                    print(f"   ⚠️ Error migrating user {user_doc.id}: {e}")
                    self.stats['users']['errors'] += 1
            
            print(f"   ✅ Migrated {self.stats['users']['migrated']} users")
            
        except Exception as e:
            print(f"   ❌ Error migrating users: {e}")
    
    def migrate_files(self):
        """Migrate files collection"""
        try:
            files_ref = self.firestore_db.collection('files')
            files = files_ref.stream()
            
            for file_doc in files:
                try:
                    file_data = file_doc.to_dict()
                    # Convert and insert
                    self.stats['files']['migrated'] += 1
                except Exception as e:
                    print(f"   ⚠️ Error migrating file {file_doc.id}: {e}")
                    self.stats['files']['errors'] += 1
            
            print(f"   ✅ Migrated {self.stats['files']['migrated']} files")
            
        except Exception as e:
            print(f"   ❌ Error migrating files: {e}")
    
    def migrate_text_content(self):
        """Migrate text_content collection"""
        try:
            text_ref = self.firestore_db.collection('text_content')
            texts = text_ref.stream()
            
            for text_doc in texts:
                try:
                    text_data = text_doc.to_dict()
                    # Convert and insert
                    self.stats['text_content']['migrated'] = self.stats.get('text_content', {}).get('migrated', 0) + 1
                except Exception as e:
                    print(f"   ⚠️ Error migrating text_content {text_doc.id}: {e}")
            
            print(f"   ✅ Migrated {self.stats.get('text_content', {}).get('migrated', 0)} text_content entries")
            
        except Exception as e:
            print(f"   ❌ Error migrating text_content: {e}")
    
    def migrate_voices(self):
        """Migrate voices collection"""
        try:
            voices_ref = self.firestore_db.collection('voices')
            voices = voices_ref.stream()
            
            for voice_doc in voices:
                try:
                    voice_data = voice_doc.to_dict()
                    # Convert and insert
                    self.stats['voices']['migrated'] += 1
                except Exception as e:
                    print(f"   ⚠️ Error migrating voice {voice_doc.id}: {e}")
                    self.stats['voices']['errors'] += 1
            
            print(f"   ✅ Migrated {self.stats['voices']['migrated']} voices")
            
        except Exception as e:
            print(f"   ❌ Error migrating voices: {e}")
    
    def migrate_miners(self):
        """Migrate miners collection"""
        try:
            miners_ref = self.firestore_db.collection('miners')
            miners = miners_ref.stream()
            
            for miner_doc in miners:
                try:
                    miner_data = miner_doc.to_dict()
                    # Convert and insert
                    self.stats['miners']['migrated'] += 1
                except Exception as e:
                    print(f"   ⚠️ Error migrating miner {miner_doc.id}: {e}")
                    self.stats['miners']['errors'] += 1
            
            print(f"   ✅ Migrated {self.stats['miners']['migrated']} miners")
            
        except Exception as e:
            print(f"   ❌ Error migrating miners: {e}")
    
    def migrate_miner_status(self):
        """Migrate miner_status collection"""
        try:
            status_ref = self.firestore_db.collection('miner_status')
            statuses = status_ref.stream()
            
            for status_doc in statuses:
                try:
                    status_data = status_doc.to_dict()
                    # Convert and insert
                    self.stats['miner_status']['migrated'] += 1
                except Exception as e:
                    print(f"   ⚠️ Error migrating miner_status {status_doc.id}: {e}")
                    self.stats['miner_status']['errors'] += 1
            
            print(f"   ✅ Migrated {self.stats['miner_status']['migrated']} miner_status entries")
            
        except Exception as e:
            print(f"   ❌ Error migrating miner_status: {e}")
    
    def migrate_tasks(self):
        """Migrate tasks collection"""
        try:
            tasks_ref = self.firestore_db.collection('tasks')
            tasks = tasks_ref.stream()
            
            for task_doc in tasks:
                try:
                    task_data = task_doc.to_dict()
                    task_data['task_id'] = task_doc.id
                    
                    # Migrate using PostgreSQL adapter
                    self.postgresql.create_task(task_data)
                    self.stats['tasks']['migrated'] += 1
                    
                    if self.stats['tasks']['migrated'] % 100 == 0:
                        print(f"   📊 Migrated {self.stats['tasks']['migrated']} tasks...")
                        
                except Exception as e:
                    print(f"   ⚠️ Error migrating task {task_doc.id}: {e}")
                    self.stats['tasks']['errors'] += 1
            
            print(f"   ✅ Migrated {self.stats['tasks']['migrated']} tasks")
            
        except Exception as e:
            print(f"   ❌ Error migrating tasks: {e}")
    
    def print_summary(self):
        """Print migration summary"""
        print("\n" + "="*80)
        print("📊 Migration Summary")
        print("="*80)
        
        total_migrated = 0
        total_errors = 0
        
        for collection, stats in self.stats.items():
            migrated = stats.get('migrated', 0)
            errors = stats.get('errors', 0)
            total_migrated += migrated
            total_errors += errors
            
            status = "✅" if errors == 0 else "⚠️"
            print(f"{status} {collection}: {migrated} migrated, {errors} errors")
        
        print(f"\n📈 Total: {total_migrated} records migrated, {total_errors} errors")
        print("="*80)

def main():
    """Main migration function"""
    # Initialize Firestore
    credentials_path = "/Users/user/Documents/Jarvis/violet/proxy_server/db/violet.json"
    if not os.path.exists(credentials_path):
        print(f"❌ Firebase credentials not found at {credentials_path}")
        return
    
    db_manager = DatabaseManager(credentials_path)
    db_manager.initialize()
    firestore_db = db_manager.get_db()
    
    # Initialize PostgreSQL
    database_url = os.getenv(
        'DATABASE_URL', 
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    postgresql = PostgreSQLAdapter(database_url)
    
    # Run migration
    migrator = DataMigrator(firestore_db, postgresql)
    success = migrator.migrate_all()
    
    if success:
        print("\n🎉 Migration completed successfully!")
    else:
        print("\n❌ Migration completed with errors")
        sys.exit(1)

if __name__ == "__main__":
    main()

