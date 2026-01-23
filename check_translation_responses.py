#!/usr/bin/env python3
"""
Check responses for translation tasks
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

# Translation task IDs from the recreation
task_ids = {
    '17ae024c-0871-420a-b5e1-d9e0af646373': 'facebook/mbart-large-50-many-to-many-mmt (en → es)',
    '6e8c5fb3-2baf-4b53-8ff0-f73076836899': 't5-small (en → es)',
    '38b1639d-0b22-483b-9962-abe84a921711': 'Helsinki-NLP/opus-mt-en-es (en → es)',
    'fd0839c5-471c-4ce1-b63f-5f36588a9459': 'Helsinki-NLP/opus-mt-en-fr (en → fr)',
    'cc050bf5-3997-4d1b-9d5b-f96637365252': 'Helsinki-NLP/opus-mt-en-de (en → de)',
    '5fc60d35-16ca-47ec-945a-3aaab2a917e7': 'Helsinki-NLP/opus-mt-en-zh (en → zh)'
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
                    source_language,
                    target_language,
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
            source_language = task[5]
            target_language = task[6]
            completed_at = task[7]
            
            response_info = {
                'task_id': task_id,
                'model_name': model_name,
                'status': status,
                'assigned_miners': assigned_miners,
                'response_count': len(miner_responses),
                'model_id': model_id,
                'source_language': source_language,
                'target_language': target_language,
                'completed_at': completed_at,
                'responses': []
            }
            
            # Extract translated text from each response
            for idx, response in enumerate(miner_responses):
                if isinstance(response, dict):
                    miner_uid = response.get('miner_uid', 'Unknown')
                    response_obj = response.get('response', {})
                    
                    # Try multiple paths to find translated_text
                    translated_text = ''
                    processing_time = 0.0
                    accuracy_score = 0.0
                    speed_score = 0.0
                    
                    # Path 1: response['response']['response_data']['output_data']['translated_text']
                    if isinstance(response_obj, dict):
                        response_data = response_obj.get('response_data', {})
                        if isinstance(response_data, dict):
                            output_data = response_data.get('output_data', {})
                            if isinstance(output_data, dict):
                                translated_text = output_data.get('translated_text', '')
                                processing_time = output_data.get('processing_time', response_data.get('processing_time', response_obj.get('processing_time', 0.0)))
                                accuracy_score = response_data.get('accuracy_score', response_obj.get('accuracy_score', 0.0))
                                speed_score = response_data.get('speed_score', response_obj.get('speed_score', 0.0))
                    
                    # Path 2: response['response_data']['output_data']['translated_text']
                    if not translated_text:
                        response_data = response.get('response_data', {})
                        if isinstance(response_data, dict):
                            output_data = response_data.get('output_data', {})
                            if isinstance(output_data, dict):
                                translated_text = output_data.get('translated_text', '')
                            else:
                                translated_text = response_data.get('translated_text', '')
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
                                        translated_text = output_data.get('translated_text', '')
                                    else:
                                        translated_text = parsed.get('translated_text', '')
                            except:
                                pass
                    
                    # Path 3: Direct translated_text key
                    if not translated_text:
                        translated_text = response.get('translated_text', '')
                    
                    # Fallback for processing_time, accuracy_score, speed_score
                    if not processing_time:
                        processing_time = response.get('processing_time', 0.0)
                    if not accuracy_score:
                        accuracy_score = response.get('accuracy_score', 0.0)
                    if not speed_score:
                        speed_score = response.get('speed_score', 0.0)
                    
                    response_info['responses'].append({
                        'miner_uid': miner_uid,
                        'translated_text': translated_text[:200] + '...' if len(translated_text) > 200 else translated_text,
                        'translated_text_length': len(translated_text),
                        'processing_time': processing_time,
                        'accuracy_score': accuracy_score,
                        'speed_score': speed_score,
                        'has_translation': bool(translated_text and translated_text.strip())
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
    print("  CHECK TRANSLATION TASK RESPONSES")
    print("=" * 80)
    print()
    
    all_results = []
    total_responses = 0
    tasks_with_responses = 0
    tasks_with_valid_translations = 0
    
    for task_id, model_name in task_ids.items():
        result = check_task_responses(task_id, model_name)
        if result:
            all_results.append(result)
            total_responses += result['response_count']
            if result['response_count'] > 0:
                tasks_with_responses += 1
                # Check if any response has a valid translation
                if any(r['has_translation'] for r in result['responses']):
                    tasks_with_valid_translations += 1
    
    # Print detailed results
    for result in all_results:
        print(f"\n{'=' * 80}")
        print(f"📋 {result['model_name']}")
        print(f"{'=' * 80}")
        print(f"Task ID: {result['task_id']}")
        print(f"Status: {result['status']}")
        print(f"Model: {result['model_id']}")
        print(f"Source Language: {result['source_language']}")
        print(f"Target Language: {result['target_language']}")
        print(f"Assigned Miners: {result['assigned_miners']}")
        print(f"Response Count: {result['response_count']}")
        print(f"Completed At: {result['completed_at']}")
        
        if result['response_count'] == 0:
            print("\n⚠️  No responses yet")
        else:
            print(f"\n📝 Responses ({result['response_count']}):")
            for idx, resp in enumerate(result['responses'], 1):
                print(f"\n   Response #{idx} (Miner UID: {resp['miner_uid']}):")
                print(f"   - Has Translation: {'✅ Yes' if resp['has_translation'] else '❌ No'}")
                if resp['has_translation']:
                    print(f"   - Translated Text Length: {resp['translated_text_length']} chars")
                    print(f"   - Translated Text Preview: {resp['translated_text']}")
                else:
                    print(f"   - Translated Text: (empty or missing)")
                print(f"   - Processing Time: {resp['processing_time']:.2f}s")
                print(f"   - Accuracy Score: {resp['accuracy_score']:.2f}")
                print(f"   - Speed Score: {resp['speed_score']:.2f}")
    
    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"\nTotal Tasks Checked: {len(all_results)}")
    print(f"Tasks with Responses: {tasks_with_responses}/{len(all_results)}")
    print(f"Tasks with Valid Translations: {tasks_with_valid_translations}/{len(all_results)}")
    print(f"Total Responses: {total_responses}")
    
    if tasks_with_responses > 0:
        print(f"\n✅ {tasks_with_responses} task(s) have received responses")
    else:
        print(f"\n⚠️  No tasks have received responses yet")
        print("   Miners may still be processing or need to poll for tasks")
    
    if tasks_with_valid_translations > 0:
        print(f"✅ {tasks_with_valid_translations} task(s) have valid translations")
    elif tasks_with_responses > 0:
        print(f"⚠️  {tasks_with_responses} task(s) have responses but no valid translations")
        print("   This may indicate the miner/proxy fixes need to be applied")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
