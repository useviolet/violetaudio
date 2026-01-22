#!/usr/bin/env python3
"""Verify task assignment to miner"""

import sys
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

database_url = os.getenv(
    'DATABASE_URL',
    'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
)
task_id = '7ac106e9-408c-46d2-9601-fe3354243f0e'

engine = create_engine(database_url, pool_pre_ping=True, connect_args={'connect_timeout': 10, 'sslmode': 'require'})
with engine.connect() as conn:
    query = text('SELECT task_id, status::text, assigned_miners, actual_miner_count, task_type FROM tasks WHERE task_id = :task_id')
    result = conn.execute(query, {'task_id': task_id})
    task = result.fetchone()
    if task:
        print(f'✅ Task Found:')
        print(f'   Task ID: {task[0]}')
        print(f'   Status: {task[1]}')
        print(f'   Assigned Miners: {task[2]}')
        print(f'   Miner Count: {task[3]}')
        print(f'   Task Type: {task[4]}')
        if task[2] and 6 in task[2]:
            print(f'\n✅ Task is assigned to miner UID 6!')
        else:
            print(f'\n❌ Task is NOT assigned to miner UID 6')
    else:
        print('❌ Task not found')
