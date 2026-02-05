#!/usr/bin/env python3
"""
Inspect summarization task response structure
"""

import sys
import os
import json
from pathlib import Path

_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

def get_database_url():
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    return database_url

# Check a task from second batch
task_id = '9ad97f46-bd24-4062-a116-74164cb24af7'

database_url = get_database_url()
engine = create_engine(database_url, pool_pre_ping=True, connect_args={'connect_timeout': 10, 'sslmode': 'require'})

print("=" * 80)
print(f"  INSPECTING TASK: {task_id}")
print("=" * 80)

with engine.connect() as conn:
    query = text('SELECT miner_responses FROM tasks WHERE task_id = CAST(:task_id AS uuid)')
    result = conn.execute(query, {'task_id': task_id})
    task = result.fetchone()
    
    if task and task[0]:
        miner_responses = task[0]
        print(f"\nNumber of responses: {len(miner_responses) if isinstance(miner_responses, list) else 'N/A'}")
        print(f"\nFull Response Structure (JSON):")
        print(json.dumps(miner_responses, indent=2, default=str))
        
        # Check first response in detail
        if isinstance(miner_responses, list) and len(miner_responses) > 0:
            first_response = miner_responses[0]
            print(f"\n" + "=" * 80)
            print("  FIRST RESPONSE DETAILS")
            print("=" * 80)
            print(f"Type: {type(first_response)}")
            print(f"Keys: {list(first_response.keys()) if isinstance(first_response, dict) else 'N/A'}")
            
            if isinstance(first_response, dict):
                for key, value in first_response.items():
                    print(f"\n{key}:")
                    print(f"  Type: {type(value)}")
                    if isinstance(value, dict):
                        print(f"  Keys: {list(value.keys())}")
                        if value:
                            print(f"  Content (first 500 chars): {str(value)[:500]}")
                    elif isinstance(value, str):
                        print(f"  Content (first 500 chars): {value[:500]}")
                    else:
                        print(f"  Value: {value}")

engine.dispose()
