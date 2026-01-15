# Active Miner Detection Fix

## Problem

The validator was incorrectly marking miners as "active" when they returned status codes **408** (Request Timeout) or **503** (Service Unavailable). This caused miners that were NOT actually running or ready to be marked as active.

### Example from Logs:
```
✅ UID   6 | 102.134.149.117:8091 | On-chain handshake: REACHABLE (busy)
```
- Status code: **503** (Service Unavailable)
- Was marked as: **ACTIVE** ❌
- Should be: **NOT ACTIVE** ✅

## Root Cause

The code was accepting multiple status codes as "active":
```python
# BEFORE (WRONG):
if status_code in [200, 400, 408, 500, 503]:
    active_miners.append(uid)  # ❌ Too lenient!
```

**Problem**: Status codes 408 and 503 don't mean the miner is ready:
- **408** = Request Timeout → Miner took too long (might be hung, overloaded, or not running properly)
- **503** = Service Unavailable → Miner is busy, down, or service not available
- **400** = Bad Request → Miner is misconfigured
- **500** = Server Error → Miner has internal errors

## Solution

**Only status code 200 means the miner is ACTIVE and READY:**

```python
# AFTER (CORRECT):
if status_code == 200:
    active_miners.append(uid)  # ✅ Only truly ready miners
else:
    # Log why miner was rejected (debug level)
    # Miner is reachable but NOT active/ready
```

## Status Code Meanings

| Status Code | Meaning | Should be Active? | Reason |
|------------|---------|------------------|--------|
| **200** | Success | ✅ **YES** | Miner is running and ready to process tasks |
| **400** | Bad Request | ❌ **NO** | Miner is misconfigured |
| **408** | Request Timeout | ❌ **NO** | Miner is too slow or not responding properly |
| **500** | Server Error | ❌ **NO** | Miner has internal errors |
| **503** | Service Unavailable | ❌ **NO** | Miner is busy, down, or service unavailable |

## Expected Behavior After Fix

### Before Fix:
- Miners with 408/503 status → Marked as **ACTIVE** ❌
- Result: Validator tries to assign tasks to miners that aren't ready
- Example: UID 6 marked as active even though not running

### After Fix:
- Only miners with 200 status → Marked as **ACTIVE** ✅
- Miners with 408/503 → Logged as "REACHABLE but NOT ACTIVE" (debug level)
- Result: Validator only assigns tasks to miners that are actually ready

## Logging Changes

### Active Miners (Status 200):
```
✅ UID   6 | 102.134.149.117:8091 | On-chain handshake: SUCCESS (Status: 200)
```

### Non-Active Miners (Status 408/503):
```
⏱️  UID   6 | 102.134.149.117:8091 | REACHABLE but NOT ACTIVE: Timeout (Status: 408) - Miner too slow
🔌 UID   6 | 102.134.149.117:8091 | REACHABLE but NOT ACTIVE: Service Unavailable (Status: 503) - Miner busy/down
```

## Impact

1. **More Accurate Detection**: Only truly ready miners are marked as active
2. **Better Task Distribution**: Tasks only go to miners that can actually process them
3. **Clearer Logging**: Debug logs show why miners were rejected
4. **Reduced Failed Tasks**: Won't try to assign tasks to unavailable miners

## Testing

After this fix, you should see:
- Fewer miners marked as "active" (only those with status 200)
- Debug logs showing why other miners were rejected
- Better task success rate (tasks only go to ready miners)

