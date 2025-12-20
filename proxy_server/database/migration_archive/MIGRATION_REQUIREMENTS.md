# PostgreSQL Migration Requirements

## What Has Been Created

### ✅ Core Infrastructure
1. **PostgreSQL Schema** (`postgresql_schema.py`)
   - SQLAlchemy models for all tables
   - Proper relationships and foreign keys
   - Indexes for performance
   - Enums matching Firestore schema

2. **Database Adapters** (`database_adapter.py`, `postgresql_adapter.py`)
   - Abstract adapter interface
   - PostgreSQL adapter implementation
   - Dual database adapter for graceful migration

3. **Migration Scripts** (`migrate_data.py`)
   - Data migration from Firestore to PostgreSQL
   - Validation and error handling
   - Progress tracking

4. **Documentation** (`MIGRATION_PLAN.md`)
   - Complete migration strategy
   - Phase-by-phase approach
   - Rollback procedures

## What You Need to Do

### 1. Set Up PostgreSQL Database

```bash
# Install PostgreSQL (if not already installed)
# macOS: brew install postgresql
# Ubuntu: sudo apt-get install postgresql

# Create database
createdb violet_proxy

# Or using psql:
psql -U postgres
CREATE DATABASE violet_proxy;
\q
```

### 2. Configure Environment Variables

Add to `.env` file:
```bash
# Database selection (start with 'dual' for migration)
DATABASE_TYPE=dual

# PostgreSQL connection
DATABASE_URL=postgresql://username:password@localhost:5432/violet_proxy

# Migration settings
MIGRATION_READ_PRIMARY=firestore
MIGRATION_DUAL_WRITE=true
```

### 3. Install Dependencies

```bash
pip install sqlalchemy>=2.0.0 psycopg2-binary>=2.9.0 alembic>=1.12.0
```

### 4. Create PostgreSQL Schema

```bash
python proxy_server/database/create_postgresql_schema.py
```

### 5. Update DatabaseOperations Class

Modify `proxy_server/database/enhanced_schema.py` to use the adapter:

```python
# At the top of the file
from .database_adapter import DualDatabaseAdapter, PostgreSQLAdapter
from .postgresql_adapter import PostgreSQLAdapter as PGAdapter

# In DatabaseOperations class, replace direct Firestore calls with adapter calls
# Example:
@staticmethod
def create_task(db, task_data: Dict[str, Any]) -> str:
    # Check if db is adapter or Firestore
    if isinstance(db, (DualDatabaseAdapter, PGAdapter)):
        return db.create_task(task_data)
    else:
        # Original Firestore code
        ...
```

### 6. Update main.py to Use Adapter

In `proxy_server/main.py` startup:

```python
from database.database_adapter import DualDatabaseAdapter, PostgreSQLAdapter
from database.postgresql_adapter import PostgreSQLAdapter as PGAdapter
from database.schema import DatabaseManager

# Initialize both databases
firestore_db = DatabaseManager(credentials_path)
firestore_db.initialize()
firestore_client = firestore_db.get_db()

# Initialize PostgreSQL
database_url = os.getenv('DATABASE_URL')
postgresql = PGAdapter(database_url)

# Create dual adapter
db_adapter = DualDatabaseAdapter(
    firestore_adapter=firestore_client,  # Need to wrap in adapter
    postgresql_adapter=postgresql
)

# Use db_adapter instead of firestore_client
```

### 7. Create Firestore Adapter Wrapper

Create `proxy_server/database/firestore_adapter.py` that wraps existing Firestore operations to match the adapter interface.

### 8. Run Migration

```bash
# Test migration on a small subset first
python proxy_server/database/migrate_data.py

# Validate migration
python proxy_server/database/validate_migration.py
```

## Migration Phases

### Phase 1: Preparation ✅
- [x] PostgreSQL schema created
- [x] Adapters created
- [ ] PostgreSQL database set up
- [ ] Dependencies installed
- [ ] Schema created in PostgreSQL

### Phase 2: Dual Write
- [ ] Firestore adapter wrapper created
- [ ] DatabaseOperations updated to use adapter
- [ ] main.py updated to use dual adapter
- [ ] Test dual write
- [ ] Monitor both databases

### Phase 3: Read Migration
- [ ] Switch read primary to PostgreSQL
- [ ] Keep Firestore as fallback
- [ ] Monitor performance
- [ ] Validate data consistency

### Phase 4: Complete Migration
- [ ] Disable Firestore writes
- [ ] Remove Firestore fallback
- [ ] Archive Firestore data
- [ ] Remove Firestore dependencies

## Key Files to Modify

1. **`proxy_server/database/enhanced_schema.py`**
   - Update `DatabaseOperations` to use adapter pattern
   - Replace direct Firestore calls

2. **`proxy_server/main.py`**
   - Initialize dual database adapter
   - Pass adapter to DatabaseOperations

3. **`proxy_server/database/firestore_adapter.py`** (NEW)
   - Wrap existing Firestore operations
   - Implement DatabaseAdapter interface

## Testing Checklist

- [ ] PostgreSQL connection works
- [ ] Schema created successfully
- [ ] Adapters work independently
- [ ] Dual adapter writes to both
- [ ] Data migration script works
- [ ] Read operations work from both
- [ ] Performance is acceptable
- [ ] Error handling works
- [ ] Rollback procedure tested

## Estimated Time

- **Setup**: 2-4 hours
- **Adapter Integration**: 4-8 hours
- **Testing**: 4-8 hours
- **Migration**: 1-2 days
- **Total**: 2-3 days for complete migration

## Support

If you encounter issues:
1. Check PostgreSQL logs
2. Verify connection string
3. Test adapters independently
4. Review migration plan document
5. Check for foreign key violations


