#!/usr/bin/env python3
"""
Diagnostic script to check why validator cannot perform handshake with miner.
This will help identify connection issues preventing miner from being reported to proxy server.
"""

import bittensor as bt
import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from template.protocol import AudioTask
import base64

# Configuration
NETWORK = "test"
NETUID = 292

MINER_WALLET_NAME = "violet_cold"
MINER_HOTKEY = "violet_hot"

VALIDATOR_WALLET_NAME = "validator"
VALIDATOR_HOTKEY = "default"

def print_section(title: str):
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")

def print_result(test_name: str, success: bool, message: str = ""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"   {status}: {test_name}")
    if message:
        print(f"      {message}")

async def test_handshake(dendrite, miner_axon, miner_uid):
    """Test the handshake that validator performs"""
    print(f"\n🔍 Testing handshake with miner UID {miner_uid}...")
    print(f"   IP: {miner_axon.ip}")
    print(f"   Port: {miner_axon.port}")
    print(f"   Is Serving: {miner_axon.is_serving}")
    
    # Create handshake task exactly as validator does
    test_text = "This is a test for handshake verification."
    handshake_task = AudioTask(
        task_type="summarization",
        input_data=base64.b64encode(test_text.encode('utf-8')).decode('utf-8'),
        language="en"
    )
    
    try:
        print(f"   Sending handshake query (timeout: 15s)...")
        start_time = datetime.now()
        
        responses = await asyncio.wait_for(
            dendrite(
                axons=[miner_axon],
                synapse=handshake_task,
                deserialize=False,
                timeout=15
            ),
            timeout=20
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if responses and len(responses) > 0:
            response = responses[0]
            
            # Check status code
            status_code = 200
            if hasattr(response, 'dendrite') and hasattr(response.dendrite, 'status_code'):
                status_code = response.dendrite.status_code
            
            print_result("Handshake Response Received", True, 
                        f"Status: {status_code}, Time: {elapsed:.2f}s")
            
            # Check if response contains handshake_ack
            if hasattr(response, 'output_data') and response.output_data:
                try:
                    decoded = base64.b64decode(response.output_data.encode('utf-8'))
                    decoded_str = decoded.decode('utf-8', errors='ignore')
                    if "handshake_ack" in decoded_str.lower():
                        print_result("Handshake Acknowledgment", True, 
                                    f"Response: {decoded_str[:50]}")
                    else:
                        print_result("Handshake Acknowledgment", False, 
                                    f"Unexpected response: {decoded_str[:50]}")
                except Exception as e:
                    print_result("Handshake Response Decode", False, str(e))
            
            return status_code in [200, 400, 500]
        else:
            print_result("Handshake Response", False, "No response received")
            return False
            
    except asyncio.TimeoutError:
        print_result("Handshake Timeout", False, 
                    "Miner did not respond within 20 seconds")
        return False
    except Exception as e:
        error_msg = str(e)
        print_result("Handshake Error", False, error_msg)
        
        # Provide specific guidance based on error type
        if "Connect" in error_msg or "Connection" in error_msg:
            print(f"\n   💡 Connection Error - Possible causes:")
            print(f"      - Miner port is not accessible (firewall/port forwarding)")
            print(f"      - Miner is not running or axon is not started")
            print(f"      - IP/Port mismatch in metagraph")
        elif "Timeout" in error_msg:
            print(f"\n   💡 Timeout Error - Possible causes:")
            print(f"      - Miner is overloaded or slow to respond")
            print(f"      - Network latency is too high")
            print(f"      - Miner is processing another task")
        
        return False

def main():
    print_section("Validator-Miner Handshake Diagnostic")
    print(f"Test started at: {datetime.now().isoformat()}")
    
    # Connect to metagraph
    print_section("Step 1: Connecting to Metagraph")
    try:
        subtensor = bt.subtensor(network=NETWORK)
        metagraph = subtensor.metagraph(netuid=NETUID)
        print_result("Metagraph Connection", True, f"Connected to netuid {NETUID}")
        print(f"   Total neurons: {len(metagraph.hotkeys)}")
    except Exception as e:
        print_result("Metagraph Connection", False, str(e))
        sys.exit(1)
    
    # Find miner
    print_section("Step 2: Finding Miner in Metagraph")
    try:
        miner_wallet = bt.wallet(name=MINER_WALLET_NAME, hotkey=MINER_HOTKEY)
        miner_hotkey_address = str(miner_wallet.hotkey.ss58_address)
        print(f"   Miner hotkey: {miner_hotkey_address}")
        
        miner_uid = None
        for uid, hotkey in enumerate(metagraph.hotkeys):
            if hotkey == miner_hotkey_address:
                miner_uid = uid
                break
        
        if miner_uid is None:
            print_result("Miner Found", False, "Miner not found in metagraph")
            sys.exit(1)
        
        print_result("Miner Found", True, f"Miner at UID {miner_uid}")
        miner_axon = metagraph.axons[miner_uid]
        print(f"   IP: {miner_axon.ip}")
        print(f"   Port: {miner_axon.port}")
        print(f"   Is Serving: {miner_axon.is_serving}")
        
    except Exception as e:
        print_result("Miner Lookup", False, str(e))
        sys.exit(1)
    
    # Test handshake
    print_section("Step 3: Testing Handshake (as Validator Does)")
    try:
        validator_wallet = bt.wallet(name=VALIDATOR_WALLET_NAME, hotkey=VALIDATOR_HOTKEY)
        validator_dendrite = bt.dendrite(wallet=validator_wallet)
        
        success = asyncio.run(test_handshake(validator_dendrite, miner_axon, miner_uid))
        
        if success:
            print_result("Overall Handshake Test", True, 
                        "Miner should be reported to proxy server")
        else:
            print_result("Overall Handshake Test", False, 
                        "Miner will NOT be reported to proxy server")
            print(f"\n   ⚠️  This is why the validator cannot find active miners!")
            print(f"   The validator requires a successful handshake before reporting to proxy.")
            
    except Exception as e:
        print_result("Handshake Test Setup", False, str(e))
        import traceback
        traceback.print_exc()
    
    # Summary
    print_section("Summary & Recommendations")
    print("\n📋 Key Points:")
    print("   1. Validator performs on-chain handshake with each miner")
    print("   2. Only miners that successfully respond are added to 'reachable_miners'")
    print("   3. Only 'reachable_miners' are reported to proxy server")
    print("   4. If handshake fails, miner is silently skipped (no error logged)")
    print("\n💡 To Fix:")
    print("   1. Ensure miner port is externally accessible")
    print("   2. Check firewall rules allow connections to miner port")
    print("   3. Verify miner axon is started and listening")
    print("   4. Check miner logs for handshake requests")
    print("   5. Consider increasing handshake timeout if network is slow")
    
    print(f"\nTest completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()

