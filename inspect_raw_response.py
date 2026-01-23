#!/usr/bin/env python3
"""
Inspect raw response data structure for a summarization task
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

# Check one task
task_id = '594aefc0-6789-478c-b008-ce38ddabb5a0'  # facebook/bart-large-cnn (First Batch)

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
                miner_responses
            FROM tasks
            WHERE task_id = CAST(:task_id AS uuid)
        """)
        
        result = conn.execute(query, {'task_id': task_id})
        task = result.fetchone()
        
        if task:
            miner_responses = task[2] or []
            
            print("=" * 80)
            print(f"RAW RESPONSE INSPECTION - Task: {task_id}")
            print("=" * 80)
            print(f"\nTotal Responses: {len(miner_responses)}")
            
            for idx, response in enumerate(miner_responses, 1):
                print(f"\n{'=' * 80}")
                print(f"Response #{idx}:")
                print(f"{'=' * 80}")
                print(f"\nRaw Response Type: {type(response)}")
                print(f"\nRaw Response (pretty-printed):")
                print(json.dumps(response, indent=2, default=str))
                
                # Try to extract summary
                print(f"\n{'─' * 80}")
                print("Summary Extraction Attempts:")
                print(f"{'─' * 80}")
                
                if isinstance(response, dict):
                    print(f"\n1. Direct 'summary' key: {response.get('summary', 'NOT FOUND')}")
                    print(f"2. 'response_data' key: {type(response.get('response_data'))}")
                    
                    response_data = response.get('response_data')
                    if response_data:
                        if isinstance(response_data, dict):
                            print(f"   - response_data['summary']: {response_data.get('summary', 'NOT FOUND')}")
                            print(f"   - response_data['output_data']: {type(response_data.get('output_data'))}")
                            
                            output_data = response_data.get('output_data')
                            if output_data:
                                if isinstance(output_data, dict):
                                    print(f"      - output_data['summary']: {output_data.get('summary', 'NOT FOUND')}")
                        elif isinstance(response_data, str):
                            print(f"   - response_data is a string, attempting to parse...")
                            try:
                                parsed = json.loads(response_data)
                                print(f"   - Parsed type: {type(parsed)}")
                                if isinstance(parsed, dict):
                                    print(f"   - parsed['summary']: {parsed.get('summary', 'NOT FOUND')}")
                                    print(f"   - parsed['output_data']: {type(parsed.get('output_data'))}")
                                    output_data = parsed.get('output_data')
                                    if isinstance(output_data, dict):
                                        print(f"      - output_data['summary']: {output_data.get('summary', 'NOT FOUND')}")
                            except Exception as e:
                                print(f"   - Failed to parse: {e}")
        
        engine.dispose()
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
