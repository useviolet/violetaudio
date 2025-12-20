#!/usr/bin/env python3
"""
Cleanup script for Firestore audio chunks
Removes old chunked audio files to prevent database bloat
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add proxy_server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def cleanup_old_chunks(max_age_days: int = 7, dry_run: bool = True):
    """
    Clean up audio chunks for completed tasks older than max_age_days
    
    Args:
        max_age_days: Delete chunks for tasks older than this many days
        dry_run: If True, only report what would be deleted without actually deleting
    """
    try:
        from firebase_admin import firestore
        import firebase_admin
        from firebase_admin import credentials
        
        credentials_path = Path(__file__).parent / "db" / "violet-rename.json"
        
        # Initialize Firebase Admin if not already initialized
        try:
            app = firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(str(credentials_path))
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        print(f"✅ Firestore client initialized")
        
        # Find completed tasks older than max_age_days
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        print(f"\n🔍 Looking for completed tasks older than {max_age_days} days (before {cutoff_date.date()})")
        
        # Query for completed tasks with chunked audio
        tasks_ref = db.collection('tasks')
        completed_tasks = tasks_ref.where('status', 'in', ['completed', 'failed', 'cancelled']).where('created_at', '<', cutoff_date).stream()
        
        tasks_to_clean = []
        total_chunks = 0
        
        for task_doc in completed_tasks:
            task_data = task_doc.to_dict()
            input_file = task_data.get('input_file', {})
            
            # Check if task has chunked audio
            if input_file.get('chunked', False) and input_file.get('storage_location') == 'database_chunked':
                chunk_count = input_file.get('chunk_count', 0)
                tasks_to_clean.append({
                    'task_id': task_doc.id,
                    'chunk_count': chunk_count,
                    'created_at': task_data.get('created_at'),
                    'status': task_data.get('status')
                })
                total_chunks += chunk_count
        
        print(f"\n📊 Found {len(tasks_to_clean)} tasks with chunked audio to clean")
        print(f"   Total chunks: {total_chunks}")
        
        if dry_run:
            print(f"\n🔍 DRY RUN - No deletions will be performed")
            print(f"\nTasks that would be cleaned:")
            for task in tasks_to_clean[:10]:  # Show first 10
                print(f"   - Task {task['task_id']}: {task['chunk_count']} chunks, status: {task['status']}")
            if len(tasks_to_clean) > 10:
                print(f"   ... and {len(tasks_to_clean) - 10} more tasks")
            return
        
        # Actually delete chunks
        print(f"\n🗑️  Deleting chunks...")
        deleted_tasks = 0
        deleted_chunks = 0
        
        for task in tasks_to_clean:
            try:
                chunks_collection = db.collection('tasks').document(task['task_id']).collection('audio_chunks')
                
                # Delete all chunks
                for chunk_doc in chunks_collection.stream():
                    chunk_doc.reference.delete()
                    deleted_chunks += 1
                
                # Update task to mark chunks as cleaned
                task_ref = db.collection('tasks').document(task['task_id'])
                task_ref.update({
                    'input_file.chunks_cleaned': True,
                    'input_file.chunks_cleaned_at': datetime.now()
                })
                
                deleted_tasks += 1
                
                if deleted_tasks % 10 == 0:
                    print(f"   ✅ Cleaned {deleted_tasks} tasks, {deleted_chunks} chunks...")
                    
            except Exception as e:
                print(f"   ⚠️  Error cleaning task {task['task_id']}: {e}")
        
        print(f"\n✅ Cleanup complete!")
        print(f"   Tasks cleaned: {deleted_tasks}")
        print(f"   Chunks deleted: {deleted_chunks}")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up old Firestore audio chunks')
    parser.add_argument('--max-age-days', type=int, default=7, help='Delete chunks for tasks older than this many days (default: 7)')
    parser.add_argument('--execute', action='store_true', help='Actually delete chunks (default is dry run)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🧹 Firestore Audio Chunks Cleanup")
    print("=" * 70)
    
    cleanup_old_chunks(max_age_days=args.max_age_days, dry_run=not args.execute)
    
    print("=" * 70)

