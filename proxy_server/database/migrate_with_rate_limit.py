#!/usr/bin/env python3
"""
Migrate data from Firestore to PostgreSQL with rate limiting and error handling
Handles Firestore quota limits by adding delays and processing in smaller batches
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from proxy_server.database.schema import DatabaseManager
from proxy_server.database.postgresql_adapter import PostgreSQLAdapter
from proxy_server.database.postgresql_schema import (
    Base, Task, TaskAssignment, File, TextContent, Miner, MinerStatus, User, Voice, SystemMetrics
)
from firebase_admin import firestore
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import json

def convert_datetime_in_json(obj):
    """Recursively convert datetime objects in JSON-serializable structures to ISO strings"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_datetime_in_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_in_json(item) for item in obj]
    elif hasattr(obj, 'timestamp'):  # Firestore Timestamp
        return datetime.fromtimestamp(obj.timestamp()).isoformat()
    else:
        return obj

def migrate_collection_with_limit(
    session: Session, 
    firestore_db, 
    collection_name: str, 
    model_class, 
    transform_func=None,
    batch_size: int = 50,
    delay_seconds: float = 1.0
):
    """Migrate a Firestore collection with rate limiting"""
    print(f"\n📦 Migrating {collection_name}...")
    print(f"   Batch size: {batch_size}, Delay: {delay_seconds}s")
    
    try:
        collection_ref = firestore_db.collection(collection_name)
        
        # Get total count first (optional, may fail with quota)
        try:
            # Try to get count (this might fail with quota)
            docs = collection_ref.limit(1).stream()
            has_data = any(True for _ in docs)
            if not has_data:
                print(f"   ℹ️ Collection {collection_name} is empty, skipping")
                return 0, 0
        except:
            pass  # Continue even if count fails
        
        # Stream documents with pagination
        migrated = 0
        errors = 0
        last_doc = None
        batch_count = 0
        
        while True:
            try:
                # Query with pagination
                query = collection_ref.limit(batch_size)
                if last_doc:
                    query = query.start_after(last_doc)
                
                docs = list(query.stream())
                
                if not docs:
                    break  # No more documents
                
                batch_count += 1
                print(f"   Processing batch {batch_count} ({len(docs)} documents)...")
                
                for doc in docs:
                    try:
                        data = doc.to_dict()
                        if not data:
                            continue
                        
                        # Use document ID if no ID field in data
                        if hasattr(model_class, '__table__'):
                            pk_col = list(model_class.__table__.primary_key.columns)[0]
                            pk_name = pk_col.name
                            
                            # Set primary key from document ID or data
                            if pk_name not in data:
                                if pk_name == 'task_id' or pk_name.endswith('_id'):
                                    data[pk_name] = doc.id
                                elif pk_name == 'uid':
                                    try:
                                        data[pk_name] = int(doc.id) if doc.id.isdigit() else doc.id
                                    except:
                                        data[pk_name] = doc.id
                                elif pk_name == 'voice_name':
                                    data[pk_name] = doc.id
                                else:
                                    data[pk_name] = doc.id
                        
                        # Transform data if function provided
                        if transform_func:
                            data = transform_func(data, doc.id)
                        
                        # Convert Firestore timestamps to datetime
                        for key, value in list(data.items()):
                            if hasattr(value, 'timestamp'):  # Firestore Timestamp
                                data[key] = datetime.fromtimestamp(value.timestamp())
                            elif isinstance(value, dict) and 'seconds' in value:  # Timestamp dict
                                data[key] = datetime.fromtimestamp(value['seconds'])
                        
                        # Filter out fields that don't exist in model
                        model_fields = {col.name for col in model_class.__table__.columns}
                        filtered_data = {k: v for k, v in data.items() if k in model_fields}
                        
                        # Handle required fields with defaults
                        if model_class == File:
                            # Ensure required fields have values
                            if not filtered_data.get('original_filename'):
                                # Try to extract from r2_key or use safe_filename
                                r2_key = filtered_data.get('r2_key', '')
                                if r2_key:
                                    filtered_data['original_filename'] = r2_key.split('/')[-1]
                                elif filtered_data.get('safe_filename'):
                                    filtered_data['original_filename'] = filtered_data['safe_filename']
                                else:
                                    filtered_data['original_filename'] = 'unknown_file'
                            
                            if not filtered_data.get('safe_filename'):
                                filtered_data['safe_filename'] = filtered_data.get('original_filename', 'unknown_file')
                        
                        # Handle JSON fields - convert datetime objects to strings
                        json_fields = ['miner_responses', 'best_response', 'evaluation_data', 'user_metadata', 'meta_data']
                        for key in json_fields:
                            if key in filtered_data and filtered_data[key] is not None:
                                filtered_data[key] = convert_datetime_in_json(filtered_data[key])
                        
                        # Handle enum conversions
                        if 'status' in filtered_data and hasattr(model_class, 'status'):
                            # Status will be handled by SQLAlchemy enum
                            pass
                        if 'priority' in filtered_data and hasattr(model_class, 'priority'):
                            pass
                        if 'task_type' in filtered_data and hasattr(model_class, 'task_type'):
                            pass
                        if 'role' in filtered_data and hasattr(model_class, 'role'):
                            pass
                        
                        # Check if record already exists (for idempotent migration)
                        pk_col = list(model_class.__table__.primary_key.columns)[0]
                        pk_name = pk_col.name
                        pk_value = filtered_data.get(pk_name)
                        
                        if pk_value:
                            existing = session.query(model_class).filter(
                                getattr(model_class, pk_name) == pk_value
                            ).first()
                            if existing:
                                print(f"      ℹ️ {model_class.__name__} {pk_value} already exists, skipping")
                                continue
                        
                        # Create model instance
                        try:
                            instance = model_class(**filtered_data)
                            session.add(instance)
                            migrated += 1
                        except Exception as e:
                            print(f"      ⚠️ Error creating {model_class.__name__} instance for {doc.id}: {e}")
                            errors += 1
                            continue
                        
                    except Exception as e:
                        errors += 1
                        print(f"      ⚠️ Error processing {doc.id}: {e}")
                        if errors > 20:
                            print(f"      ⚠️ Too many errors, stopping batch")
                            break
                
                # Commit batch
                try:
                    session.commit()
                    print(f"      ✅ Committed batch {batch_count} ({migrated} total migrated)")
                except Exception as e:
                    session.rollback()
                    print(f"      ❌ Error committing batch: {e}")
                    errors += len(docs)
                
                # Update last_doc for pagination
                if docs:
                    last_doc = docs[-1]
                
                # Rate limiting delay
                if len(docs) == batch_size:  # More data might be available
                    time.sleep(delay_seconds)
                
                # Break if too many errors
                if errors > 50:
                    print(f"      ⚠️ Too many errors ({errors}), stopping migration")
                    break
                    
            except Exception as e:
                error_msg = str(e)
                if "Quota exceeded" in error_msg or "429" in error_msg:
                    print(f"      ⚠️ Firestore quota exceeded, waiting 60 seconds...")
                    time.sleep(60)
                    continue  # Retry
                elif "429" in error_msg:
                    print(f"      ⚠️ Rate limit hit, waiting 30 seconds...")
                    time.sleep(30)
                    continue
                else:
                    print(f"      ❌ Error in batch: {e}")
                    errors += batch_size
                    break
        
        print(f"   ✅ Completed {collection_name}: {migrated} migrated, {errors} errors")
        return migrated, errors
        
    except Exception as e:
        session.rollback()
        print(f"   ❌ Error migrating {collection_name}: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

def transform_task_data(data: dict, doc_id: str) -> dict:
    """Transform task data for PostgreSQL"""
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
    
    # Ensure assigned_miners is a list
    if 'assigned_miners' in data:
        if not isinstance(data['assigned_miners'], list):
            data['assigned_miners'] = []
    
    # Map status values to enum values
    status_mapping = {
        'processing': 'in_progress',
        'pending': 'pending',
        'assigned': 'assigned',
        'in_progress': 'in_progress',
        'completed': 'completed',
        'approved': 'approved',
        'failed': 'failed',
        'cancelled': 'cancelled'
    }
    if 'status' in data and data['status'] in status_mapping:
        data['status'] = status_mapping[data['status']]
    
    return data

def migrate_voices_with_file_check(
    session: Session,
    firestore_db,
    batch_size: int = 20,
    delay_seconds: float = 2.0
):
    """Migrate voices with file existence check"""
    print(f"📦 Migrating voices (with file validation)...")
    print(f"   Batch size: {batch_size}, Delay: {delay_seconds}s")
    
    migrated = 0
    errors = 0
    
    try:
        voices_ref = firestore_db.collection('voices')
        docs = list(voices_ref.stream())
        
        for doc in docs:
            try:
                data = doc.to_dict()
                if not data:
                    continue
                
                # Check if referenced file exists
                file_id = data.get('file_id')
                if file_id:
                    from proxy_server.database.postgresql_schema import File
                    file_exists = session.query(File).filter(File.file_id == file_id).first()
                    if not file_exists:
                        print(f"      ⚠️ Skipping voice {doc.id}: referenced file {file_id} not found")
                        # Make file_id nullable for this record
                        data['file_id'] = None
                
                # Set primary key
                data['voice_name'] = doc.id
                
                # Convert timestamps
                for key, value in list(data.items()):
                    if hasattr(value, 'timestamp'):
                        data[key] = datetime.fromtimestamp(value.timestamp())
                
                # Filter to model fields
                model_fields = {col.name for col in Voice.__table__.columns}
                filtered_data = {k: v for k, v in data.items() if k in model_fields}
                
                # Ensure required fields
                if not filtered_data.get('display_name'):
                    filtered_data['display_name'] = filtered_data.get('voice_name', 'Unknown')
                if not filtered_data.get('file_name'):
                    filtered_data['file_name'] = filtered_data.get('voice_name', 'unknown.wav')
                
                # Check if already exists
                existing = session.query(Voice).filter(Voice.voice_name == doc.id).first()
                if existing:
                    print(f"      ℹ️ Voice {doc.id} already exists, skipping")
                    continue
                
                instance = Voice(**filtered_data)
                session.add(instance)
                migrated += 1
                
            except Exception as e:
                errors += 1
                print(f"      ⚠️ Error processing voice {doc.id}: {e}")
        
        session.commit()
        print(f"   ✅ Completed voices: {migrated} migrated, {errors} errors")
        return migrated, errors
        
    except Exception as e:
        session.rollback()
        print(f"   ❌ Error migrating voices: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

def migrate_task_assignments(
    session: Session,
    firestore_db,
    batch_size: int = 30,
    delay_seconds: float = 1.5
):
    """Migrate task assignments - can be from separate collection or embedded in tasks"""
    print(f"📦 Migrating task_assignments...")
    print(f"   Batch size: {batch_size}, Delay: {delay_seconds}s")
    
    migrated = 0
    errors = 0
    
    try:
        # First, try to migrate from separate task_assignments collection
        try:
            assignments_ref = firestore_db.collection('task_assignments')
            docs = list(assignments_ref.limit(1).stream())
            
            if docs:
                print("   Found separate task_assignments collection, migrating...")
                result = migrate_collection_with_limit(
                    session, firestore_db, 'task_assignments', TaskAssignment,
                    batch_size=batch_size, delay_seconds=delay_seconds
                )
                return result
        except Exception as e:
            print(f"   ℹ️ No separate task_assignments collection: {e}")
        
        # If no separate collection, extract from tasks.task_assignments
        print("   Extracting assignments from tasks.task_assignments field...")
        tasks_ref = firestore_db.collection('tasks')
        tasks = tasks_ref.stream()
        
        batch = []
        for task_doc in tasks:
            try:
                task_data = task_doc.to_dict()
                task_id = task_doc.id
                task_assignments = task_data.get('task_assignments', [])
                
                if not task_assignments:
                    continue
                
                for assignment_data in task_assignments:
                    if not isinstance(assignment_data, dict):
                        continue
                    
                    # Create TaskAssignment record
                    assignment = {
                        'assignment_id': assignment_data.get('assignment_id', str(uuid.uuid4())),
                        'task_id': task_id,
                        'miner_uid': assignment_data.get('miner_uid'),
                        'status': assignment_data.get('status', 'pending'),
                    }
                    
                    # Handle timestamps
                    if 'assigned_at' in assignment_data:
                        assigned_at = assignment_data['assigned_at']
                        if hasattr(assigned_at, 'timestamp'):
                            assignment['assigned_at'] = datetime.fromtimestamp(assigned_at.timestamp())
                        elif isinstance(assigned_at, datetime):
                            assignment['assigned_at'] = assigned_at
                        else:
                            assignment['assigned_at'] = datetime.utcnow()
                    else:
                        assignment['assigned_at'] = datetime.utcnow()
                    
                    if 'completed_at' in assignment_data:
                        completed_at = assignment_data['completed_at']
                        if hasattr(completed_at, 'timestamp'):
                            assignment['completed_at'] = datetime.fromtimestamp(completed_at.timestamp())
                        elif isinstance(completed_at, datetime):
                            assignment['completed_at'] = completed_at
                    
                    if assignment.get('miner_uid') is None:
                        continue
                    
                    # Filter to only include fields that exist in model
                    model_fields = {col.name for col in TaskAssignment.__table__.columns}
                    filtered_assignment = {k: v for k, v in assignment.items() if k in model_fields}
                    
                    # Check if task exists (foreign key constraint)
                    from proxy_server.database.postgresql_schema import Task
                    task_exists = session.query(Task).filter(Task.task_id == task_id).first()
                    if not task_exists:
                        print(f"      ⚠️ Skipping assignment for non-existent task {task_id}")
                        continue
                    
                    try:
                        instance = TaskAssignment(**filtered_assignment)
                        batch.append(instance)
                        migrated += 1
                    except Exception as e:
                        print(f"      ⚠️ Error creating assignment: {e}")
                        errors += 1
                        continue
                
                # Commit in batches
                if len(batch) >= batch_size:
                    try:
                        session.add_all(batch)
                        session.commit()
                        print(f"      ✅ Committed batch ({migrated} total migrated)")
                        batch = []
                        time.sleep(delay_seconds)
                    except Exception as e:
                        session.rollback()
                        print(f"      ❌ Error committing batch: {e}")
                        errors += len(batch)
                        batch = []
                        
            except Exception as e:
                errors += 1
                print(f"      ⚠️ Error processing task {task_doc.id}: {e}")
        
        # Commit remaining batch
        if batch:
            try:
                session.add_all(batch)
                session.commit()
                print(f"      ✅ Committed final batch ({migrated} total migrated)")
            except Exception as e:
                session.rollback()
                print(f"      ❌ Error committing final batch: {e}")
                errors += len(batch)
        
        print(f"   ✅ Completed task_assignments: {migrated} migrated, {errors} errors")
        return migrated, errors
        
    except Exception as e:
        session.rollback()
        print(f"   ❌ Error migrating task_assignments: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

def main():
    """Main migration function"""
    print("="*80)
    print("🚀 Starting Data Migration: Firestore → PostgreSQL")
    print("   (With rate limiting and error handling)")
    print("="*80)
    
    # Initialize Firestore
    credentials_path = "/Users/user/Documents/Jarvis/violet/proxy_server/db/violet.json"
    if not os.path.exists(credentials_path):
        print(f"❌ Firebase credentials not found at {credentials_path}")
        return False
    
    print("\n1️⃣ Initializing Firestore...")
    try:
        db_manager = DatabaseManager(credentials_path)
        db_manager.initialize()
        firestore_db = db_manager.get_db()
        print("   ✅ Firestore connected")
    except Exception as e:
        print(f"   ❌ Failed to connect to Firestore: {e}")
        return False
    
    # Initialize PostgreSQL
    print("\n2️⃣ Initializing PostgreSQL...")
    try:
        database_url = 'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
        postgresql = PostgreSQLAdapter(database_url)
        print("   ✅ PostgreSQL connected")
    except Exception as e:
        print(f"   ❌ Failed to connect to PostgreSQL: {e}")
        return False
    
    # Get session
    session = postgresql._get_session()
    
    stats = {}
    
    try:
        # Migrate in dependency order with rate limiting
        print("\n3️⃣ Starting data migration (with rate limiting)...")
        print("   Note: This may take a while due to Firestore rate limits")
        
        # Users first (no dependencies) - small batch
        print("\n" + "-"*80)
        stats['users'] = migrate_collection_with_limit(
            session, firestore_db, 'users', User, 
            batch_size=20, delay_seconds=2.0
        )
        
        # Files (no dependencies)
        print("\n" + "-"*80)
        stats['files'] = migrate_collection_with_limit(
            session, firestore_db, 'files', File,
            batch_size=30, delay_seconds=1.5
        )
        
        # Text content (no dependencies)
        print("\n" + "-"*80)
        stats['text_content'] = migrate_collection_with_limit(
            session, firestore_db, 'text_content', TextContent,
            batch_size=30, delay_seconds=1.5
        )
        
        # Voices (depends on files) - migrate after files are done
        print("\n" + "-"*80)
        stats['voices'] = migrate_voices_with_file_check(
            session, firestore_db, batch_size=20, delay_seconds=2.0
        )
        
        # Miners (no dependencies)
        print("\n" + "-"*80)
        stats['miners'] = migrate_collection_with_limit(
            session, firestore_db, 'miners', Miner,
            batch_size=20, delay_seconds=2.0
        )
        
        # Miner status (depends on miners)
        print("\n" + "-"*80)
        stats['miner_status'] = migrate_collection_with_limit(
            session, firestore_db, 'miner_status', MinerStatus,
            batch_size=30, delay_seconds=1.5
        )
        
        # Tasks (depends on files, text_content, users) - larger, slower
        print("\n" + "-"*80)
        stats['tasks'] = migrate_collection_with_limit(
            session, firestore_db, 'tasks', Task, transform_task_data,
            batch_size=25, delay_seconds=2.5  # Slower for tasks
        )
        
        # Task assignments (depends on tasks, miners) - extract from tasks or separate collection
        print("\n" + "-"*80)
        stats['task_assignments'] = migrate_task_assignments(
            session, firestore_db, batch_size=30, delay_seconds=1.5
        )
        
        # System metrics (optional, no dependencies)
        print("\n" + "-"*80)
        stats['system_metrics'] = migrate_collection_with_limit(
            session, firestore_db, 'system_metrics', SystemMetrics,
            batch_size=50, delay_seconds=1.0
        )
        
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
            print("   You may need to run the migration again for failed records")
            return False
            
    except KeyboardInterrupt:
        session.rollback()
        print("\n\n⚠️ Migration interrupted by user")
        print("   Partial data may have been migrated")
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


