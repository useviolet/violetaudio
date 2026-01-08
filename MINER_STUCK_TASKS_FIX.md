# Miner Stuck Tasks Fix

## Problem Identified

The miner was continuously processing the same old tasks that were stuck in "assigned" status. These tasks were:
- Created in December 2025 (20+ days old)
- Still in "assigned" status in the database
- Never marked as completed or failed
- Kept appearing every time the miner queried for tasks

### Example Stuck Tasks:
- `7b414944-29b0-4187-8374-4f04ec4f2b75` (TTS, created Dec 18, 2025)
- `b9d4b916-8505-457f-a60a-9507512d267f` (TTS, created Dec 18, 2025)
- `67a3bf5e-1537-4cc6-9518-f1526285dd90` (TTS, created Dec 18, 2025)
- `07228f7c-e922-4e93-8597-e177676b097b` (Transcription, created Jan 7, 2026)

## Root Cause

1. **No Age Filter**: The miner was processing tasks regardless of their age
2. **Stuck Status**: Tasks remained in "assigned" status even after being processed
3. **No Completion Tracking**: Tasks weren't being marked as completed in the database after processing
4. **Infinite Loop**: Old tasks kept appearing in every query cycle

## Solution Implemented

### 1. Added Age Filter (24 hours)
The miner now automatically skips tasks older than 24 hours:

```python
max_task_age_hours = 24  # Skip tasks older than 24 hours
max_task_age_seconds = max_task_age_hours * 60 * 60

# Check task age and skip if too old
if task_age_seconds > max_task_age_seconds:
    bt.logging.warning(f"⏭️  Skipping old task {task_id} - {task_age_hours:.1f} hours old")
    self.processed_tasks.add(task_id)  # Mark as processed to prevent reprocessing
    continue
```

### 2. Automatic Marking
Old tasks are automatically marked as "processed" in the miner's memory to prevent them from being queried again.

### 3. Better Logging
The miner now logs when it skips old tasks, making it clear why certain tasks aren't being processed.

## Benefits

1. **Prevents Infinite Loops**: Old stuck tasks won't keep appearing
2. **Reduces Processing Load**: Miner focuses on recent, valid tasks
3. **Clearer Logs**: You can see why tasks are being skipped
4. **Better Resource Usage**: CPU and memory aren't wasted on old tasks

## What Happens Now

When the miner starts:
1. It queries for assigned tasks
2. Filters out tasks older than 24 hours
3. Logs a warning for each skipped old task
4. Only processes recent, valid tasks
5. Old tasks are marked as processed to prevent future queries

## Next Steps (Optional)

If you want to clean up the database:
1. Mark old stuck tasks as "failed" or "cancelled" in the database
2. Update the proxy server to automatically expire old tasks
3. Add a cleanup job to mark tasks older than 24 hours as failed

## Testing

After restarting the miner, you should see:
- Warnings like: `⏭️  Skipping old task {task_id} - {days} days old`
- Only recent tasks being processed
- No more infinite loops of old tasks

