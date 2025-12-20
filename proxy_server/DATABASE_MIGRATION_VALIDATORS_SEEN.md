# Database Migration: Add validators_seen Columns

## Issue
The code references `validators_seen` and `validators_seen_timestamps` columns in the `tasks` table, but these columns don't exist in the database, causing SQL errors:
```
column tasks.validators_seen does not exist
```

## Solution
1. **Updated `_task_to_dict` method** in `postgresql_adapter.py` to safely access these fields using `getattr` with defaults
2. **Created migration script** to add the columns to the database
3. **Fixed missing variable** in `main.py` (validators_seen was missing)

## Migration Steps

### Option 1: Run the migration script
```bash
cd proxy_server
python run_migration_validators_seen.py
```

### Option 2: Run SQL manually
Connect to your PostgreSQL database and run:
```sql
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS validators_seen JSONB DEFAULT '[]'::jsonb;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS validators_seen_timestamps JSONB DEFAULT '{}'::jsonb;
```

## What These Columns Do
- **`validators_seen`**: JSON array of validator identifiers that have processed/rewarded this task
- **`validators_seen_timestamps`**: JSON object mapping validator identifiers to timestamps when they processed the task

These columns prevent duplicate rewards by tracking which validators have already evaluated a task.

## Files Changed
1. `proxy_server/database/postgresql_adapter.py` - Added safe access to validators_seen fields
2. `proxy_server/database/migrations/add_validators_seen_columns.py` - Migration script
3. `proxy_server/run_migration_validators_seen.py` - Quick runner script
4. `proxy_server/main.py` - Fixed missing variable (already present)

## Testing
After running the migration, the proxy server should start without the "column does not exist" errors.

