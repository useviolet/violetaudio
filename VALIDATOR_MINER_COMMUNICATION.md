# Validator-Miner Communication Guide

## How It Works

The validator and miner communicate via the **Bittensor metagraph** and **on-chain handshake**:

1. **Metagraph Registration**: Both miner and validator register their IP/port on-chain
2. **On-Chain Handshake**: Validator sends a test query to each miner to verify they're online
3. **Proxy Server Reporting**: Validator reports only miners that passed the handshake to the proxy server

## The Flow

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Miner     │────────▶│  Metagraph   │◀────────│ Validator   │
│  (Port 8091)│         │  (On-Chain)  │         │ (Port 8092) │
└─────────────┘         └──────────────┘         └─────────────┘
       │                                              │
       │                                              │
       │         ┌──────────────────────┐            │
       └────────▶│  On-Chain Handshake  │◀───────────┘
                 │  (Network Connection)│
                 └──────────────────────┘
                        │
                        │ (Only if successful)
                        ▼
                 ┌──────────────────────┐
                 │   Proxy Server        │
                 │   (Miner Status DB)   │
                 └──────────────────────┘
```

## Why Handshake is Required

The validator requires a successful **on-chain handshake** before reporting miners to the proxy server because:

1. **Verification**: Confirms the miner is actually online and responsive
2. **Network Accessibility**: Verifies the miner's port is accessible
3. **Quality Control**: Only active, reachable miners are reported

## Current Status

✅ **Metagraph Communication**: Working - Both miner and validator are registered  
✅ **Handshake Test**: Working - Diagnostic test shows successful handshake (1.36s response)  
❓ **Validator Detection**: Unknown - Need to check validator logs

## What We Fixed

1. **Bug Fix**: Fixed `serving_miners` counter (was incorrectly indented)
2. **Better Logging**: Added debug logs for connection errors and timeouts
3. **Diagnostic Script**: Created `diagnose_handshake.py` to test handshake

## Troubleshooting

### If Validator Cannot Find Miners

1. **Check Validator Logs** for:
   - `🔍 Performing on-chain handshake with serving miners...`
   - `✅ UID X | IP:PORT | On-chain handshake: SUCCESS`
   - `⚠️  On-chain handshake: No active miners found`

2. **Check Miner Logs** for:
   - `🤝 On-chain handshake received - responding immediately`
   - Connection errors or timeouts

3. **Verify Network**:
   - Miner port (8091) is externally accessible
   - Firewall allows connections
   - Router port forwarding configured (if behind NAT)

4. **Check Configuration**:
   - `VALIDATOR_API_KEY` is set (required for proxy reporting)
   - Miner and validator are on the same network (test/finney)
   - Correct netuid (292 for test network)

### Running Diagnostics

```bash
# Test handshake connectivity
python3 diagnose_handshake.py

# Test full validator-miner connection
python3 test_validator_miner_connection.py
```

## Key Code Locations

- **Validator Handshake**: `neurons/validator.py:344` - `check_miner_connectivity()`
- **Miner Handshake Handler**: `neurons/miner.py:3035` - Handles handshake requests
- **Proxy Reporting**: `neurons/validator.py:1184` - `report_miner_status_to_proxy()`

## Next Steps

1. **Check Validator Logs**: Look for handshake attempts and results
2. **Verify VALIDATOR_API_KEY**: Ensure it's set in validator environment
3. **Monitor Handshake**: Watch for successful handshakes in validator logs
4. **Check Proxy Server**: Verify miners are being reported to proxy database

## Summary

The validator **requires** a successful network handshake (not just metagraph registration) before reporting miners to the proxy server. This ensures only active, reachable miners are available for task distribution.

If the handshake test passes but the validator still doesn't find miners, check:
- Validator is actually running the handshake check
- VALIDATOR_API_KEY is set
- Validator logs show handshake attempts
- No errors preventing handshake execution

