#!/usr/bin/env python3
"""Check what enum values exist in the database"""

import sys
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

database_url = os.getenv(
    'DATABASE_URL',
    'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
)

engine = create_engine(database_url, pool_pre_ping=True, connect_args={'connect_timeout': 10, 'sslmode': 'require'})
with engine.connect() as conn:
    # Get all enum values
    query = text("""
        SELECT enumlabel 
        FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'taskstatusenum')
        ORDER BY enumsortorder
    """)
    result = conn.execute(query)
    values = [row[0] for row in result.fetchall()]
    
    print(f"Available TaskStatusEnum values:")
    for val in values:
        print(f"  - {val}")
