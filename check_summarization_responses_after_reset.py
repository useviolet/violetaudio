#!/usr/bin/env python3
"""
Check responses for reset summarization tasks
"""

import sys
import os
from pathlib import Path

_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
import json

def get_database_url():
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

# All summarization task IDs from both batches
task_ids = {
    # First batch (Bobi Wine text)
    '594aefc0-6789-478c-b008-ce38ddabb5a0': 'facebook/bart-large-cnn (First Batch)',
    '90ecc2a3-59c1-48a1-88e7-a66fdea3f0ca': 'facebook/bart-base (First Batch)',
    '9d6671d9-ece0-4d57-9b7e-97ec1fa6d2ff': 'google/pegasus-xsum (First Batch)',
    '8269b54d-5aef-4cbe-a813-fc62a2f4c0ce': 't5-small (First Batch)',
    
    # Second batch (AI text)
    '9ad97f46-bd24-4062-a116-74164cb24af7': 'facebook/bart-large-cnn (Second Batch)',
    'edbda16f-cd04-4fa2-bdcd-6be0071baa70': 'facebook/bart-base (Second Batch)',
    'e31d71e1-c954-4b9c-a26e-f8c4cdde18f1': 'google/pegasus-xsum (Second Batch)',
    'a178536a-3466-4e85-a25b-ea50637309d2': 't5-small (Second Batch)'
}

def check_task_responses(task_id, model_name):
    """Check responses for a task"""
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
            query = text("""
                SELECT 
                    task_id,
                    status::text,
                    assigned_miners,
                    miner_responses,
                    model_id,
                    completed_at
                FROM tasks
                WHERE task_id = CAST(:task_id AS uuid)
            """)
            
            result = conn.execute(query, {'task_id': task_id})
            task = result.fetchone()
            
            if not task:
                print(f"❌ Task {task_id} not found")
                return None
            
            status = task[1]
            assigned_miners = task[2] or []
            miner_responses = task[3] or []
            model_id = task[4]
            completed_at = task[5]
            
            response_info = {
                'task_id': task_id,
                'model_name': model_name,
                'status': status,
                'assigned_miners': assigned_miners,
                'response_count': len(miner_responses),
                'model_id': model_id,
                'completed_at': completed_at,
                'responses': []
            }
            
            # Extract summary from each response
            for idx, response in enumerate(miner_responses):
                if isinstance(response, dict):
                    miner_uid = response.get('miner_uid', 'Unknown')
                    
                    # Try multiple paths to find summary
                    summary = ''
                    processing_time = 0.0
                    accuracy_score = 0.0
                    speed_score = 0.0
                    
                    # Path 1: response['response']['response_data']['output_data']['summary']
                    response_obj = response.get('response', {})
                    if isinstance(response_obj, dict):
                        response_data = response_obj.get('response_data', {})
                        if isinstance(response_data, dict):
                            output_data = response_data.get('output_data', {})
                            if isinstance(output_data, dict):
                                summary = output_data.get('summary', '')
                                processing_time = output_data.get('processing_time', response_data.get('processing_time', response_obj.get('processing_time', 0.0)))
                                accuracy_score = response_data.get('accuracy_score', response_obj.get('accuracy_score', 0.0))
                                speed_score = response_data.get('speed_score', response_obj.get('speed_score', 0.0))
                    
                    # Path 2: response['response_data']['output_data']['summary']
                    if not summary:
                        response_data = response.get('response_data', {})
                        if isinstance(response_data, dict):
                            output_data = response_data.get('output_data', {})
                            if isinstance(output_data, dict):
                                summary = output_data.get('summary', '')
                            else:
                                summary = response_data.get('summary', '')
                            if not processing_time:
                                processing_time = response_data.get('processing_time', 0.0)
                            if not accuracy_score:
                                accuracy_score = response_data.get('accuracy_score', 0.0)
                            if not speed_score:
                                speed_score = response_data.get('speed_score', 0.0)
                        elif isinstance(response_data, str):
                            try:
                                parsed = json.loads(response_data)
                                if isinstance(parsed, dict):
                                    output_data = parsed.get('output_data', {})
                                    if isinstance(output_data, dict):
                                        summary = output_data.get('summary', '')
                                    else:
                                        summary = parsed.get('summary', '')
                            except:
                                pass
                    
                    # Path 3: Direct summary key
                    if not summary:
                        summary = response.get('summary', '')
                    
                    # Fallback for processing_time, accuracy_score, speed_score
                    if not processing_time:
                        processing_time = response.get('processing_time', 0.0)
                    if not accuracy_score:
                        accuracy_score = response.get('accuracy_score', 0.0)
                    if not speed_score:
                        speed_score = response.get('speed_score', 0.0)
                    
                    response_info['responses'].append({
                        'miner_uid': miner_uid,
                        'summary': summary[:100] + '...' if len(summary) > 100 else summary,
                        'summary_length': len(summary),
                        'processing_time': processing_time,
                        'accuracy_score': accuracy_score,
                        'speed_score': speed_score,
                        'has_summary': bool(summary and summary.strip())
                    })
            
            engine.dispose()
            return response_info
        
    except Exception as e:
        print(f"❌ Error checking task: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("\n" + "=" * 80)
    print("  CHECK SUMMARIZATION TASK RESPONSES (After Reset)")
    print("=" * 80)
    print()
    
    all_results = []
    total_responses = 0
    tasks_with_responses = 0
    tasks_with_valid_summaries = 0
    
    for task_id, model_name in task_ids.items():
        result = check_task_responses(task_id, model_name)
        if result:
            all_results.append(result)
            total_responses += result['response_count']
            if result['response_count'] > 0:
                tasks_with_responses += 1
                # Check if any response has a valid summary
                if any(r['has_summary'] for r in result['responses']):
                    tasks_with_valid_summaries += 1
    
    # Print detailed results
    for result in all_results:
        print(f"\n{'=' * 80}")
        print(f"📋 {result['model_name']}")
        print(f"{'=' * 80}")
        print(f"Task ID: {result['task_id']}")
        print(f"Status: {result['status']}")
        print(f"Model: {result['model_id']}")
        print(f"Assigned Miners: {result['assigned_miners']}")
        print(f"Response Count: {result['response_count']}")
        print(f"Completed At: {result['completed_at']}")
        
        if result['response_count'] == 0:
            print("\n⚠️  No responses yet")
        else:
            print(f"\n📝 Responses ({result['response_count']}):")
            for idx, resp in enumerate(result['responses'], 1):
                print(f"\n   Response #{idx} (Miner UID: {resp['miner_uid']}):")
                print(f"   - Has Summary: {'✅ Yes' if resp['has_summary'] else '❌ No'}")
                if resp['has_summary']:
                    print(f"   - Summary Length: {resp['summary_length']} chars")
                    print(f"   - Summary Preview: {resp['summary']}")
                else:
                    print(f"   - Summary: (empty or missing)")
                print(f"   - Processing Time: {resp['processing_time']:.2f}s")
                print(f"   - Accuracy Score: {resp['accuracy_score']:.2f}")
                print(f"   - Speed Score: {resp['speed_score']:.2f}")
    
    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"\nTotal Tasks Checked: {len(all_results)}")
    print(f"Tasks with Responses: {tasks_with_responses}/{len(all_results)}")
    print(f"Tasks with Valid Summaries: {tasks_with_valid_summaries}/{len(all_results)}")
    print(f"Total Responses: {total_responses}")
    
    if tasks_with_responses > 0:
        print(f"\n✅ {tasks_with_responses} task(s) have received responses")
    else:
        print(f"\n⚠️  No tasks have received responses yet")
        print("   Miners may still be processing or need to poll for tasks")
    
    if tasks_with_valid_summaries > 0:
        print(f"✅ {tasks_with_valid_summaries} task(s) have valid summaries")
    elif tasks_with_responses > 0:
        print(f"⚠️  {tasks_with_responses} task(s) have responses but no valid summaries")
        print("   This may indicate the miner/proxy fixes need to be applied")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
