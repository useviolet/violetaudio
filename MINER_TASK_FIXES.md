# Miner Task Re-processing Fixes

## Issues Fixed

### 1. **Infinite Task Retries** ✅
**Problem**: Failed tasks were never marked as processed, causing infinite retries

**Solution**:
- Added retry counter (`task_retry_count`) to track failed attempts
- Tasks are marked as processed after `max_task_retries` (3) failed attempts
- Prevents infinite retry loops

### 2. **Stuck Tasks** ✅
**Problem**: Tasks stuck in `processing_tasks` forever (e.g., interrupted TTS tasks)

**Solution**:
- Added `processing_tasks_timestamps` to track when tasks started
- Added `cleanup_stuck_tasks()` function to clean up tasks stuck > 10 minutes
- Automatic cleanup on each query cycle

### 3. **Too Frequent Queries** ✅
**Problem**: Miner queried proxy server every 10 seconds, causing spam

**Solution**:
- Increased query interval from 10s to 60s
- Reduces unnecessary network traffic and logging

### 4. **No Timeout Detection** ✅
**Problem**: No way to detect or clean up stuck tasks

**Solution**:
- Added timeout check in task filtering (10 minutes)
- Stuck tasks are automatically cleaned up and marked as processed

## Code Changes

### File: `neurons/miner.py`

1. **Added Tracking Variables** (line ~133-140):
   ```python
   self.processing_tasks_timestamps = {}  # Track start times
   self.task_processing_timeout = 600  # 10 minutes
   self.max_task_retries = 3  # Max retries
   self.task_retry_count = {}  # Track retries per task
   ```

2. **Increased Query Interval** (line ~80):
   - Changed from 10s to 60s

3. **Enhanced Task Filtering** (line ~674-690):
   - Added timeout check for stuck tasks
   - Added retry limit check
   - Automatic cleanup of stuck tasks

4. **Task Processing Tracking** (line ~911):
   - Records timestamp when task starts processing

5. **Retry Logic** (line ~1316-1330):
   - Increments retry count on failure
   - Marks as processed after max retries

6. **Stuck Task Cleanup** (line ~3350+):
   - New `cleanup_stuck_tasks()` function
   - Called on each query cycle
   - Cleans up tasks stuck > 10 minutes

## Expected Behavior

### Before:
- Tasks retried forever on failure
- Stuck tasks never cleaned up
- Queries every 10 seconds
- No timeout detection

### After:
- Tasks retry max 3 times, then marked as processed
- Stuck tasks cleaned up after 10 minutes
- Queries every 60 seconds
- Automatic timeout detection and cleanup

## Configuration

- **Query Interval**: 60 seconds
- **Processing Timeout**: 600 seconds (10 minutes)
- **Max Retries**: 3 attempts
- **Max Processed Tasks**: 1000 (memory limit)

## Testing

To verify the fixes:

1. **Check for stuck tasks**:
   ```bash
   # Look for cleanup messages
   grep "Cleaned up stuck task" logs/miner/*.log
   ```

2. **Check retry behavior**:
   ```bash
   # Look for retry messages
   grep "retry" logs/miner/*.log
   ```

3. **Check query frequency**:
   ```bash
   # Should see queries every 60s, not 10s
   grep "querying proxy server" logs/miner/*.log | head -20
   ```

## Next Steps

1. Restart miner to apply changes
2. Monitor logs for:
   - Stuck task cleanup messages
   - Retry limit messages
   - Reduced query frequency
3. Verify tasks are not being reprocessed

