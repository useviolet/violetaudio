#!/usr/bin/env python3
"""
Comprehensive analysis of task structure and miner transcription pipeline
"""

import sys
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
import json

def get_database_url():
    """Get database URL from environment or use default"""
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

def print_section(title: str):
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")

def analyze_task_structure(task_id: str):
    """Analyze the complete task structure from database"""
    print_section(f"Task Structure Analysis: {task_id}")
    
    database_url = get_database_url()
    
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 10,
                "sslmode": "require"
            }
        )
        
        with engine.connect() as conn:
            # Get complete task details including input_file_id
            query = text("""
                SELECT 
                    task_id,
                    task_type::text as task_type,
                    status::text as status,
                    priority::text as priority,
                    created_at,
                    updated_at,
                    distributed_at,
                    completed_at,
                    assigned_miners,
                    required_miner_count,
                    min_miner_count,
                    max_miner_count,
                    actual_miner_count,
                    miner_responses,
                    best_response,
                    validators_seen,
                    model_id,
                    source_language,
                    target_language,
                    input_file_id,
                    voice_name,
                    speaker_wav_url,
                    user_id,
                    callback_url,
                    user_metadata
                FROM tasks
                WHERE task_id = :task_id
            """)
            
            result = conn.execute(query, {'task_id': task_id})
            task = result.fetchone()
            
            if not task:
                print(f"\n❌ Task {task_id} not found in database")
                return None
            
            (task_id_db, task_type, status, priority, created_at, updated_at,
             distributed_at, completed_at, assigned_miners, required_count,
             min_count, max_count, actual_count, miner_responses, 
             best_response, validators_seen, model_id, source_language,
             target_language, input_file_id, voice_name, speaker_wav_url,
             user_id, callback_url, user_metadata) = task
            
            # Get file information if input_file_id exists
            file_info = None
            if input_file_id:
                file_query = text("""
                    SELECT 
                        file_id,
                        original_filename,
                        safe_filename,
                        file_type,
                        file_size,
                        content_type,
                        storage_location,
                        public_url,
                        r2_bucket,
                        r2_key,
                        created_at,
                        updated_at
                    FROM files
                    WHERE file_id = :file_id
                """)
                file_result = conn.execute(file_query, {'file_id': input_file_id})
                file_info = file_result.fetchone()
            
            # Calculate timings
            now = datetime.now(timezone.utc)
            
            if created_at:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_hours = (now - created_at).total_seconds() / 3600
            else:
                age_hours = 0
            
            print(f"\n📋 Task Basic Information:")
            print(f"   Task ID: {task_id_db}")
            print(f"   Type: {task_type}")
            print(f"   Status: {status}")
            print(f"   Priority: {priority}")
            print(f"   Model ID: {model_id if model_id else 'Not specified (default: openai/whisper-tiny)'}")
            print(f"   Source Language: {source_language if source_language else 'en (default)'}")
            print(f"   Target Language: {target_language if target_language else 'N/A'}")
            print(f"   Age: {age_hours:.2f} hours")
            
            print(f"\n📁 Input File Information:")
            if input_file_id:
                print(f"   Input File ID: {input_file_id}")
                if file_info:
                    (file_id, original_filename, safe_filename, file_type, file_size, 
                     content_type, storage_location, public_url, r2_bucket, r2_key,
                     file_created_at, file_updated_at) = file_info
                    print(f"   Original Filename: {original_filename}")
                    print(f"   Safe Filename: {safe_filename}")
                    print(f"   File Type: {file_type}")
                    print(f"   Content Type: {content_type}")
                    print(f"   File Size: {file_size} bytes ({file_size/1024:.2f} KB)" if file_size else "   File Size: Unknown")
                    print(f"   Storage Location: {storage_location}")
                    print(f"   R2 Bucket: {r2_bucket}")
                    print(f"   R2 Key: {r2_key[:80] + '...' if r2_key and len(r2_key) > 80 else r2_key}")
                    print(f"   Public URL: {public_url[:80] + '...' if public_url and len(public_url) > 80 else public_url}")
                    print(f"   File Created: {file_created_at}")
                else:
                    print(f"   ⚠️  File record not found in database")
            else:
                print(f"   ⚠️  No input_file_id specified")
            
            print(f"\n⏰ Timestamps:")
            print(f"   Created: {created_at}")
            print(f"   Updated: {updated_at}")
            print(f"   Distributed: {distributed_at}")
            print(f"   Completed: {completed_at}")
            
            print(f"\n👥 Assignment Details:")
            print(f"   Required Miners: {required_count}")
            print(f"   Min Miners: {min_count}")
            print(f"   Max Miners: {max_count}")
            print(f"   Actual Miners: {actual_count}")
            if assigned_miners:
                print(f"   Assigned Miners: {assigned_miners}")
            else:
                print(f"   Assigned Miners: None")
            
            print(f"\n📊 Response Details:")
            if miner_responses:
                print(f"   Miner Responses: {len(miner_responses)} response(s)")
                for i, resp in enumerate(miner_responses):
                    print(f"      Response {i+1}:")
                    if isinstance(resp, dict):
                        print(f"         {json.dumps(resp, indent=10)}")
                    else:
                        print(f"         {resp}")
            else:
                print(f"   Miner Responses: None (0 responses)")
            
            print(f"   Best Response: {best_response if best_response else 'None'}")
            
            if validators_seen:
                print(f"   Validators Seen: {len(validators_seen)} validator(s)")
            else:
                print(f"   Validators Seen: None (0 validators)")
            
            if user_metadata:
                print(f"\n👤 User Metadata:")
                print(f"   {json.dumps(user_metadata, indent=3)}")
            
            if callback_url:
                print(f"\n🔗 Callback URL: {callback_url}")
            
            return {
                'task_id': task_id_db,
                'task_type': task_type,
                'status': status,
                'model_id': model_id,
                'source_language': source_language,
                'input_file_id': input_file_id,
                'file_info': file_info,
                'assigned_miners': assigned_miners,
                'miner_responses': miner_responses,
                'age_hours': age_hours
            }
        
        engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Error analyzing task: {e}")
        import traceback
        traceback.print_exc()
        return None

def analyze_miner_pipeline():
    """Analyze the miner transcription pipeline flow"""
    print_section("Miner Transcription Pipeline Analysis")
    
    print("\n📝 Transcription Pipeline Flow:")
    print("\n1. Task Query Phase:")
    print("   - Miner queries proxy: GET /api/v1/miners/{miner_uid}/tasks?status=assigned")
    print("   - Filters: skips processed tasks, old tasks (>24h), currently processing")
    print("   - Only processes 'assigned' or 'pending' status tasks")
    
    print("\n2. Task Processing Phase (process_proxy_task):")
    print("   a) Extract task data:")
    print("      - task_id, task_type, model_id, source_language")
    print("      - input_file_id or input_file dict")
    print("   b) Get file URL:")
    print("      - Check task_data['input_file']['public_url']")
    print("      - Or fetch from /api/v1/files/{input_file_id}")
    print("      - Or fetch from /api/v1/miner/transcription/{task_id}")
    print("   c) Download audio file:")
    print("      - Download from R2 URL (public_url)")
    print("      - Validate file size > 0 bytes")
    print("      - Check for suspiciously small files (<1KB)")
    print("   d) Process transcription:")
    print("      - Call process_transcription_task(audio_data, model_id, language)")
    print("      - Load pipeline: pipeline_manager.get_transcription_pipeline(model_id)")
    print("      - Validate audio data (bytes, non-empty)")
    print("      - Call pipeline.transcribe(audio_data, language)")
    print("   e) Submit result:")
    print("      - Validate result has transcript content")
    print("      - Call submit_result_to_proxy()")
    print("      - POST to /api/v1/miner/response")
    
    print("\n3. Potential Failure Points:")
    print("   ❌ File URL not found:")
    print("      - Missing input_file_id in task")
    print("      - Missing public_url in input_file dict")
    print("      - API endpoints return errors")
    print("   ❌ File download fails:")
    print("      - R2 URL inaccessible")
    print("      - Network timeout")
    print("      - File is empty or corrupted")
    print("   ❌ Pipeline not available:")
    print("      - Model not loaded")
    print("      - Pipeline initialization failed")
    print("   ❌ Processing fails:")
    print("      - Audio data invalid")
    print("      - Language not supported")
    print("      - Transcription pipeline error")
    print("   ❌ Submission fails:")
    print("      - Result validation fails (empty transcript)")
    print("      - API authentication fails")
    print("      - Network error during submission")
    print("      - Proxy server rejects response")

def analyze_task_issues(task_data: Optional[Dict]):
    """Analyze specific issues with the task"""
    print_section("Task Issue Analysis")
    
    if not task_data:
        print("\n❌ Cannot analyze - task data not available")
        return
    
    task_id = task_data.get('task_id')
    status = task_data.get('status')
    input_file_id = task_data.get('input_file_id')
    file_info = task_data.get('file_info')
    assigned_miners = task_data.get('assigned_miners')
    miner_responses = task_data.get('miner_responses')
    age_hours = task_data.get('age_hours', 0)
    
    issues = []
    recommendations = []
    
    print(f"\n🔍 Issue Analysis for Task {task_id}:")
    
    # Check file availability
    if not input_file_id:
        issues.append("❌ No input_file_id in task - miner cannot locate file")
        recommendations.append("   → Check task creation - ensure input_file_id is set")
    elif not file_info:
        issues.append("❌ File record not found in database")
        recommendations.append("   → File may have been deleted or never created")
    else:
        file_size = file_info[4] if file_info else None
        public_url = file_info[7] if file_info else None
        
        if not public_url:
            issues.append("❌ No public_url in file record - miner cannot download file")
            recommendations.append("   → File may not be uploaded to R2 storage")
        elif file_size and file_size == 0:
            issues.append("❌ File size is 0 bytes - file is empty")
            recommendations.append("   → Check file upload process")
        elif file_size and file_size < 1000:
            issues.append("⚠️  File size < 1KB - suspiciously small for audio")
            recommendations.append("   → File may be corrupted")
    
    # Check assignment
    if not assigned_miners or len(assigned_miners) == 0:
        issues.append("❌ No miners assigned to task")
        recommendations.append("   → Task may not have been distributed")
    elif len(assigned_miners) < task_data.get('required_miner_count', 3):
        issues.append(f"⚠️  Only {len(assigned_miners)} miner(s) assigned, need {task_data.get('required_miner_count', 3)}")
        recommendations.append("   → Task may be waiting for more miners")
    
    # Check responses
    if not miner_responses or len(miner_responses) == 0:
        issues.append("❌ No miner responses recorded")
        if age_hours > 2:
            issues.append(f"⚠️  Task has been assigned for {age_hours:.2f} hours with no responses")
            recommendations.append("   → Check if assigned miners are online")
            recommendations.append("   → Check miner logs for processing errors")
            recommendations.append("   → Verify miner can access file URL")
    
    # Check status
    if status == 'assigned' and age_hours > 24:
        issues.append("❌ Task stuck in 'assigned' status for >24 hours")
        recommendations.append("   → Task may need to be reset or reassigned")
    
    if issues:
        print("\n🚨 Issues Found:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ No obvious issues found")
    
    if recommendations:
        print("\n💡 Recommendations:")
        for rec in recommendations:
            print(rec)

def main():
    task_id = "d550c420-e1b0-41cd-a8ba-60222e86622c"
    
    print_section("Task & Pipeline Analysis")
    print(f"Analyzing task ID: {task_id}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Analyze task structure
    task_data = analyze_task_structure(task_id)
    
    # Analyze miner pipeline
    analyze_miner_pipeline()
    
    # Analyze specific issues
    analyze_task_issues(task_data)
    
    print(f"\n✅ Analysis completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()

