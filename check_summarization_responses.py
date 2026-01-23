#!/usr/bin/env python3
"""
Check all summarization tasks for responses
"""

import sys
import os
from pathlib import Path

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
import json

BASE_URL = "https://violet-proxy-bl4w.onrender.com"

def get_database_url():
    """Get database URL from environment or use default"""
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

def check_task_responses(task_ids, batch_name):
    """Check tasks for responses"""
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
        
        results = {}
        
        with engine.connect() as conn:
            for task_id, model_name in task_ids.items():
                print(f"\n{'=' * 80}")
                print(f"  TASK: {model_name} ({batch_name})")
                print(f"{'=' * 80}")
                print(f"Task ID: {task_id}")
                
                # Get task info
                query = text("""
                    SELECT 
                        task_id,
                        task_type::text,
                        status::text,
                        model_id,
                        miner_responses,
                        created_at,
                        updated_at
                    FROM tasks
                    WHERE task_id = CAST(:task_id AS uuid)
                """)
                
                result = conn.execute(query, {'task_id': task_id})
                task = result.fetchone()
                
                if not task:
                    print(f"❌ Task not found")
                    results[task_id] = {
                        'model': model_name,
                        'batch': batch_name,
                        'status': 'NOT_FOUND',
                        'response_count': 0,
                        'responses': []
                    }
                    continue
                
                task_type = task[1]
                status = task[2]
                model_id = task[3]
                miner_responses = task[4]
                created_at = task[5]
                updated_at = task[6]
                
                print(f"Status: {status}")
                print(f"Model ID: {model_id}")
                print(f"Created: {created_at}")
                print(f"Updated: {updated_at}")
                
                responses = []
                
                if miner_responses and isinstance(miner_responses, list) and len(miner_responses) > 0:
                    print(f"\n✅ Found {len(miner_responses)} response(s)")
                    
                    for idx, response in enumerate(miner_responses, 1):
                        if isinstance(response, dict):
                            miner_uid = response.get('miner_uid', 'Unknown')
                            response_data = response.get('response_data', {})
                            
                            # Debug: Print full response structure
                            print(f"\n  Response #{idx} (Miner UID: {miner_uid}):")
                            print(f"    Full Response Structure:")
                            print(f"      Keys: {list(response.keys())}")
                            print(f"      Response Data Type: {type(response_data)}")
                            if isinstance(response_data, dict):
                                print(f"      Response Data Keys: {list(response_data.keys())}")
                                if response_data:
                                    print(f"      Response Data (first 500 chars): {str(response_data)[:500]}")
                            elif isinstance(response_data, str):
                                print(f"      Response Data (first 500 chars): {response_data[:500]}")
                            
                            # Try multiple paths to find summary
                            summary = ''
                            output_data = {}
                            
                            # Path 1: response_data.output_data.summary
                            if isinstance(response_data, dict):
                                output_data = response_data.get('output_data', {})
                                if isinstance(output_data, dict):
                                    summary = output_data.get('summary', '')
                            
                            # Path 2: response_data.summary (direct)
                            if not summary and isinstance(response_data, dict):
                                summary = response_data.get('summary', '')
                            
                            # Path 3: Check if response_data is a string (JSON)
                            if not summary and isinstance(response_data, str):
                                try:
                                    import json
                                    parsed = json.loads(response_data)
                                    if isinstance(parsed, dict):
                                        output_data = parsed.get('output_data', {})
                                        if isinstance(output_data, dict):
                                            summary = output_data.get('summary', '')
                                        if not summary:
                                            summary = parsed.get('summary', '')
                                except:
                                    pass
                            
                            processing_time = response_data.get('processing_time', response.get('processing_time', 0.0)) if isinstance(response_data, dict) else response.get('processing_time', 0.0)
                            accuracy_score = response.get('accuracy_score', 0.0)
                            speed_score = response.get('speed_score', 0.0)
                            submitted_at = response.get('submitted_at', 'Unknown')
                            
                            print(f"    Submitted At: {submitted_at}")
                            print(f"    Processing Time: {processing_time:.2f}s")
                            print(f"    Accuracy Score: {accuracy_score:.2f}")
                            print(f"    Speed Score: {speed_score:.2f}")
                            
                            if summary:
                                print(f"    ✅ Summary:")
                                print(f"       {summary[:200]}{'...' if len(summary) > 200 else ''}")
                                print(f"       Length: {len(summary)} characters")
                                
                                responses.append({
                                    'miner_uid': miner_uid,
                                    'summary': summary,
                                    'summary_length': len(summary),
                                    'processing_time': processing_time,
                                    'accuracy_score': accuracy_score,
                                    'speed_score': speed_score,
                                    'submitted_at': str(submitted_at)
                                })
                            else:
                                error = output_data.get('error', response_data.get('error', 'No summary found') if isinstance(response_data, dict) else 'Empty response_data')
                                print(f"    ❌ No summary (Error: {error})")
                                responses.append({
                                    'miner_uid': miner_uid,
                                    'summary': '',
                                    'error': error,
                                    'processing_time': processing_time,
                                    'submitted_at': str(submitted_at)
                                })
                else:
                    print(f"\n⚠️  No responses yet")
                    responses = []
                
                results[task_id] = {
                    'model': model_name,
                    'batch': batch_name,
                    'status': status,
                    'model_id': model_id,
                    'response_count': len(miner_responses) if miner_responses else 0,
                    'responses': responses
                }
        
        engine.dispose()
        return results
        
    except Exception as e:
        print(f"❌ Error querying tasks: {e}")
        import traceback
        traceback.print_exc()
        return {}

def main():
    # First batch (Bobi Wine text)
    first_batch = {
        '594aefc0-6789-478c-b008-ce38ddabb5a0': 'facebook/bart-large-cnn',
        '90ecc2a3-59c1-48a1-88e7-a66fdea3f0ca': 'facebook/bart-base',
        '9d6671d9-ece0-4d57-9b7e-97ec1fa6d2ff': 'google/pegasus-xsum',
        '8269b54d-5aef-4cbe-a813-fc62a2f4c0ce': 't5-small'
    }
    
    # Second batch (AI text)
    second_batch = {
        '9ad97f46-bd24-4062-a116-74164cb24af7': 'facebook/bart-large-cnn',
        'edbda16f-cd04-4fa2-bdcd-6be0071baa70': 'facebook/bart-base',
        'e31d71e1-c954-4b9c-a26e-f8c4cdde18f1': 'google/pegasus-xsum',
        'a178536a-3466-4e85-a25b-ea50637309d2': 't5-small'
    }
    
    print("\n" + "=" * 80)
    print("  SUMMARIZATION TASK RESPONSE CHECKER")
    print("=" * 80)
    
    print("\n" + "=" * 80)
    print("  FIRST BATCH (Bobi Wine Text)")
    print("=" * 80)
    first_results = check_task_responses(first_batch, "First Batch")
    
    print("\n" + "=" * 80)
    print("  SECOND BATCH (AI Text)")
    print("=" * 80)
    second_results = check_task_responses(second_batch, "Second Batch")
    
    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY - ALL TASKS")
    print("=" * 80)
    
    all_results = {**first_results, **second_results}
    
    total_responses = 0
    total_tasks = len(all_results)
    tasks_with_responses = 0
    tasks_completed = 0
    
    for task_id, info in all_results.items():
        model = info['model']
        batch = info['batch']
        status = info['status']
        response_count = info.get('response_count', 0)
        responses = info.get('responses', [])
        
        total_responses += response_count
        if response_count > 0:
            tasks_with_responses += 1
        if status == 'COMPLETED':
            tasks_completed += 1
        
        print(f"\n📋 {model} ({batch})")
        print(f"   Task ID: {task_id}")
        print(f"   Status: {status}")
        print(f"   Responses: {response_count}")
        
        if responses:
            for idx, resp in enumerate(responses, 1):
                miner_uid = resp.get('miner_uid', 'Unknown')
                summary = resp.get('summary', '')
                if summary:
                    print(f"\n   Response #{idx} (Miner {miner_uid}):")
                    print(f"      Summary: {summary[:150]}{'...' if len(summary) > 150 else ''}")
                    print(f"      Length: {len(summary)} chars")
                    print(f"      Processing Time: {resp.get('processing_time', 0):.2f}s")
                else:
                    print(f"\n   Response #{idx} (Miner {miner_uid}):")
                    print(f"      ❌ Error: {resp.get('error', 'No summary')}")
        else:
            print(f"   ⚠️  No responses available")
    
    print(f"\n{'=' * 80}")
    print(f"Total Tasks: {total_tasks}")
    print(f"Tasks with Responses: {tasks_with_responses}")
    print(f"Tasks Completed: {tasks_completed}")
    print(f"Total Responses: {total_responses}")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    main()
