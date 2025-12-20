# Migration Explanation: What the TODOs Mean

## Summary

You want to **fully shift from Firestore to PostgreSQL** (not gradual migration). Here's what the remaining TODOs mean and what we'll do instead.

## What the TODOs Were For (Gradual Migration - NOT What You Want)

### ❌ TODO #8: "Create Firestore adapter wrapper"
**What it meant**: Create a wrapper class that makes Firestore look like the `DatabaseAdapter` interface, so the same code could work with both databases during a gradual transition.

**Why you DON'T need it**: Since you want a full shift, we'll update code to use PostgreSQL directly instead of wrapping Firestore.

### ✅ TODO #9: "Update DatabaseOperations to use adapter"  
**What it means**: Refactor `DatabaseOperations` class to use PostgreSQL adapter instead of direct Firestore calls (`db.collection()`).

**What we'll do**: Update all methods in `DatabaseOperations` to use PostgreSQL adapter methods.

### ❌ TODO #10: "Update main.py to initialize dual adapter"
**What it meant**: Change startup to use a dual adapter that writes to both databases during transition.

**Why you DON'T need it**: We'll directly use PostgreSQL adapter in `main.py` instead.

## Direct Migration Plan (What You Actually Want)

### Step 1: Update DatabaseOperations ✅ (TODO #9)
Replace all Firestore operations in `enhanced_schema.py`:
- `db.collection('tasks').document(task_id).set(data)` → `postgresql_adapter.create_task(data)`
- `db.collection('tasks').where(...).stream()` → `postgresql_adapter.get_tasks_by_status(...)`
- etc.

### Step 2: Update main.py
Replace:
```python
db_manager = DatabaseManager(credentials_path)  # Firestore
db = db_manager.get_db()
```

With:
```python
from database.postgresql_adapter import PostgreSQLAdapter
db = PostgreSQLAdapter(database_url)
```

### Step 3: Update All Managers
Find all files using `db.collection()` and update them to use adapter methods:
- `managers/task_manager.py`
- `managers/file_manager.py`
- `managers/miner_response_handler.py`
- `orchestrators/workflow_orchestrator.py`
- `api/validator_integration.py`
- etc.

### Step 4: Remove Firestore Dependencies
Once everything works, remove Firebase imports and credentials.

## Files That Need Updates

Based on search, these files use Firestore directly:
1. `proxy_server/main.py` - Startup and endpoints
2. `proxy_server/database/enhanced_schema.py` - DatabaseOperations class
3. `proxy_server/managers/task_manager.py`
4. `proxy_server/managers/file_manager.py`
5. `proxy_server/managers/miner_response_handler.py`
6. `proxy_server/orchestrators/workflow_orchestrator.py`
7. `proxy_server/api/validator_integration.py`
8. `proxy_server/managers/miner_status_manager.py`
9. `proxy_server/orchestrators/task_distributor.py`
10. And several others...

## Next Steps

I'll start by:
1. ✅ Updating `DatabaseOperations` to use PostgreSQL adapter
2. ✅ Updating `main.py` startup
3. ✅ Then updating managers one by one

Ready to proceed?

