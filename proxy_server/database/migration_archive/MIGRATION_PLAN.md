# Database Migration Plan: Firestore to PostgreSQL

## Overview
This document outlines the strategy for gracefully migrating from Firestore (NoSQL) to PostgreSQL (SQL) while maintaining system availability.

## Migration Strategy

### Phase 1: Preparation (Current)
1. ✅ Create PostgreSQL schema (SQLAlchemy models)
2. ✅ Create database adapter interface
3. ✅ Create PostgreSQL adapter implementation
4. ✅ Create dual database adapter for transition
5. ⏳ Set up PostgreSQL database
6. ⏳ Test PostgreSQL adapter independently

### Phase 2: Dual Write (Migration Period)
1. Deploy dual database adapter
2. Write to both Firestore and PostgreSQL
3. Read from Firestore (primary) with PostgreSQL validation
4. Monitor both databases for consistency
5. Gradually increase PostgreSQL read traffic

### Phase 3: Read Migration
1. Switch read primary to PostgreSQL
2. Keep Firestore as fallback
3. Monitor error rates and performance
4. Validate data consistency

### Phase 4: Complete Migration
1. Disable Firestore writes
2. Remove Firestore fallback
3. Archive Firestore data
4. Remove Firestore dependencies

## Database Schema Mapping

### Firestore Collections → PostgreSQL Tables

| Firestore Collection | PostgreSQL Table | Notes |
|---------------------|------------------|-------|
| `tasks` | `tasks` | Main task management |
| `files` | `files` | File metadata |
| `text_content` | `text_content` | Text content for tasks |
| `miners` | `miners` | Miner registration |
| `miner_status` | `miner_status` | Current miner status |
| `task_assignments` | `task_assignments` | Task-to-miner assignments |
| `miner_responses` | Embedded in `tasks.miner_responses` | JSON field |
| `users` | `users` | User accounts |
| `user_emails` | Index on `users.email` | Unique constraint |
| `api_keys` | Index on `users.api_key` | Unique constraint |
| `voices` | `voices` | TTS voice mappings |
| `system_metrics` | `system_metrics` | System statistics |

## Key Differences

### Firestore (NoSQL)
- Document-based storage
- Flexible schema
- No joins (denormalized data)
- Array fields for relationships
- Timestamp objects

### PostgreSQL (SQL)
- Relational tables
- Strict schema with foreign keys
- Joins for relationships
- JSON fields for flexible data
- DateTime columns

## Migration Scripts

### 1. Data Migration Script
```bash
python proxy_server/database/migrate_data.py
```
- Reads all data from Firestore
- Transforms to PostgreSQL format
- Writes to PostgreSQL
- Validates data integrity

### 2. Schema Creation Script
```bash
python proxy_server/database/create_postgresql_schema.py
```
- Creates all tables
- Creates indexes
- Sets up foreign keys

### 3. Validation Script
```bash
python proxy_server/database/validate_migration.py
```
- Compares data between databases
- Reports discrepancies
- Validates referential integrity

## Configuration

### Environment Variables
```bash
# Database selection
DATABASE_TYPE=dual  # firestore, postgresql, or dual

# PostgreSQL connection
DATABASE_URL=postgresql://user:password@localhost:5432/violet_proxy

# Migration settings
MIGRATION_READ_PRIMARY=firestore  # Start with Firestore
MIGRATION_DUAL_WRITE=true  # Write to both
```

## Rollback Plan

If issues occur during migration:

1. **Immediate Rollback**: Switch `DATABASE_TYPE=firestore`
2. **Data Recovery**: Use Firestore as source of truth
3. **Fix Issues**: Address PostgreSQL problems
4. **Retry Migration**: Start from Phase 2 again

## Performance Considerations

### PostgreSQL Advantages
- Better for complex queries
- ACID transactions
- Better for analytics
- Lower cost at scale
- Better for relational data

### Migration Challenges
- Array fields → Join tables or JSON
- Timestamp handling
- Denormalized data → Normalized schema
- Real-time updates → Polling or triggers

## Testing Checklist

- [ ] PostgreSQL schema created
- [ ] Adapters tested independently
- [ ] Dual adapter tested
- [ ] Data migration script tested
- [ ] Read/write operations validated
- [ ] Performance benchmarks
- [ ] Error handling tested
- [ ] Rollback procedure tested

## Timeline Estimate

- **Phase 1**: 1-2 days (setup and testing)
- **Phase 2**: 1 week (dual write period)
- **Phase 3**: 1 week (read migration)
- **Phase 4**: 1-2 days (complete migration)

**Total**: ~2-3 weeks for safe migration

## Next Steps

1. Set up PostgreSQL database
2. Run schema creation script
3. Test PostgreSQL adapter
4. Create data migration script
5. Begin Phase 2 (dual write)


