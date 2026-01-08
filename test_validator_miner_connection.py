#!/usr/bin/env python3
"""
Test script to diagnose why a validator cannot find/connect to a miner
Tests network connectivity, metagraph registration, and synapse communication
"""

import sys
import os
import asyncio
import socket
import time
from datetime import datetime
from typing import Optional, Dict, Any

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import bittensor as bt
from template.protocol import AudioTask

def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_result(test_name: str, success: bool, message: str = ""):
    """Print test result"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {test_name}")
    if message:
        print(f"   {message}")

def test_network_connectivity(ip: str, port: int, timeout: int = 5) -> bool:
    """Test if a port is open and accessible"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"   Error: {e}")
        return False

def find_miner_in_metagraph(metagraph, hotkey_address: str) -> Optional[int]:
    """Find miner UID by hotkey address in metagraph"""
    for uid in range(len(metagraph.hotkeys)):
        if str(metagraph.hotkeys[uid]) == hotkey_address:
            return uid
    return None

def find_validator_in_metagraph(metagraph, hotkey_address: str) -> Optional[int]:
    """Find validator UID by hotkey address in metagraph"""
    for uid in range(len(metagraph.hotkeys)):
        if str(metagraph.hotkeys[uid]) == hotkey_address:
            return uid
    return None

async def test_synapse_communication(dendrite, axon, test_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test actual synapse communication"""
    try:
        synapse = AudioTask(
            task_type=test_data.get('task_type', 'transcription'),
            input_data=test_data.get('input_data', 'test'),
            source_language=test_data.get('source_language', 'en')
        )
        
        start_time = time.time()
        response = await dendrite([axon], synapse=synapse, deserialize=True, timeout=30.0)
        elapsed_time = time.time() - start_time
        
        if response and len(response) > 0:
            return {
                'success': True,
                'response': response[0],
                'elapsed_time': elapsed_time,
                'error': None
            }
        else:
            return {
                'success': False,
                'response': None,
                'elapsed_time': elapsed_time,
                'error': 'No response received'
            }
    except Exception as e:
        return {
            'success': False,
            'response': None,
            'elapsed_time': 0,
            'error': str(e)
        }

def main():
    """Main test function"""
    print_section("Validator-Miner Connection Diagnostic Test")
    print(f"Test started at: {datetime.now().isoformat()}")
    
    # Configuration
    NETUID = 292
    NETWORK = "test"
    
    # Miner configuration
    MINER_IP = "188.166.63.103"
    MINER_PORT = 8091
    MINER_WALLET_NAME = "violet_cold"
    MINER_HOTKEY = "violet_hot"
    
    # Validator configuration
    VALIDATOR_IP = "188.166.63.103"
    VALIDATOR_PORT = 8092
    VALIDATOR_WALLET_NAME = "validator"
    VALIDATOR_HOTKEY = "default"
    
    print(f"\n📋 Configuration:")
    print(f"   Network: {NETWORK}")
    print(f"   NetUID: {NETUID}")
    print(f"\n   Miner:")
    print(f"      IP: {MINER_IP}")
    print(f"      Port: {MINER_PORT}")
    print(f"      Wallet: {MINER_WALLET_NAME}/{MINER_HOTKEY}")
    print(f"\n   Validator:")
    print(f"      IP: {VALIDATOR_IP}")
    print(f"      Port: {VALIDATOR_PORT}")
    print(f"      Wallet: {VALIDATOR_WALLET_NAME}/{VALIDATOR_HOTKEY}")
    
    # Test 1: Network Connectivity
    print_section("Test 1: Network Connectivity")
    
    print(f"\n🔍 Testing miner port {MINER_IP}:{MINER_PORT}...")
    miner_port_open = test_network_connectivity(MINER_IP, MINER_PORT)
    print_result("Miner Port Open", miner_port_open, 
                 f"Port {MINER_PORT} on {MINER_IP} is {'open' if miner_port_open else 'closed/blocked'}")
    
    print(f"\n🔍 Testing validator port {VALIDATOR_IP}:{VALIDATOR_PORT}...")
    validator_port_open = test_network_connectivity(VALIDATOR_IP, VALIDATOR_PORT)
    print_result("Validator Port Open", validator_port_open,
                 f"Port {VALIDATOR_PORT} on {VALIDATOR_IP} is {'open' if validator_port_open else 'closed/blocked'}")
    
    if not miner_port_open:
        print("\n⚠️  WARNING: Miner port is not accessible!")
        print("   Possible causes:")
        print("   - Miner is not running")
        print("   - Firewall is blocking the port")
        print("   - Port forwarding is not configured")
        print("   - Miner axon is not started")
    
    # Test 2: Bittensor Metagraph Connection
    print_section("Test 2: Bittensor Metagraph Connection")
    
    try:
        print(f"\n🔍 Connecting to Bittensor {NETWORK} network (netuid {NETUID})...")
        subtensor = bt.subtensor(network=NETWORK)
        metagraph = subtensor.metagraph(NETUID)
        print_result("Metagraph Connection", True, f"Connected to netuid {NETUID}")
        
        print(f"\n📊 Metagraph Information:")
        print(f"   Total neurons: {len(metagraph.hotkeys)}")
        print(f"   Block: {metagraph.block}")
        
    except Exception as e:
        print_result("Metagraph Connection", False, str(e))
        print("\n❌ Cannot proceed without metagraph connection")
        return
    
    # Test 3: Miner Registration in Metagraph
    print_section("Test 3: Miner Registration in Metagraph")
    
    try:
        print(f"\n🔍 Loading miner wallet: {MINER_WALLET_NAME}/{MINER_HOTKEY}...")
        miner_wallet = bt.wallet(name=MINER_WALLET_NAME, hotkey=MINER_HOTKEY)
        miner_hotkey_address = str(miner_wallet.hotkey.ss58_address)
        print(f"   Miner hotkey: {miner_hotkey_address}")
        
        miner_uid = find_miner_in_metagraph(metagraph, miner_hotkey_address)
        
        if miner_uid is not None:
            print_result("Miner Registered", True, f"Miner found at UID {miner_uid}")
            
            # Get miner axon information
            miner_axon = metagraph.axons[miner_uid]
            miner_stake = metagraph.S[miner_uid]
            
            print(f"\n📊 Miner Information from Metagraph:")
            print(f"   UID: {miner_uid}")
            print(f"   IP: {miner_axon.ip}")
            print(f"   Port: {miner_axon.port}")
            # Check if external IP/port attributes exist
            external_ip = getattr(miner_axon, 'ip_external', None)
            external_port = getattr(miner_axon, 'port_external', None)
            if external_ip:
                print(f"   External IP: {external_ip}")
            if external_port:
                print(f"   External Port: {external_port}")
            print(f"   Stake: {miner_stake}")
            print(f"   Is Serving: {metagraph.axons[miner_uid].is_serving}")
            
            # Check if IP/port match
            ip_match = miner_axon.ip == MINER_IP or (external_ip and external_ip == MINER_IP)
            port_match = miner_axon.port == MINER_PORT or (external_port and external_port == MINER_PORT)
            
            print(f"\n🔍 IP/Port Verification:")
            ip_str = f"{miner_axon.ip}"
            if external_ip:
                ip_str += f"/{external_ip}"
            port_str = f"{miner_axon.port}"
            if external_port:
                port_str += f"/{external_port}"
            
            print_result("IP Matches", ip_match, 
                        f"Metagraph IP ({ip_str}) vs Expected ({MINER_IP})")
            print_result("Port Matches", port_match,
                        f"Metagraph Port ({port_str}) vs Expected ({MINER_PORT})")
            
            if not ip_match or not port_match:
                print("\n⚠️  WARNING: IP/Port mismatch!")
                print("   The miner's registered IP/port in metagraph doesn't match the expected values")
                print("   This could cause connection issues")
                print("\n   💡 Solution:")
                print("   - Restart miner with correct --axon.ip and --axon.port")
                print("   - Ensure --axon.external_ip and --axon.external_port match if behind NAT")
        else:
            print_result("Miner Registered", False, "Miner not found in metagraph")
            print("\n⚠️  WARNING: Miner is not registered in the metagraph!")
            print("   Possible causes:")
            print("   - Miner has not registered on-chain")
            print("   - Miner is using different wallet/hotkey")
            print("   - Miner registration failed")
            print("   - Wrong network/netuid")
            
    except Exception as e:
        print_result("Miner Registration Check", False, str(e))
        import traceback
        traceback.print_exc()
    
    # Test 4: Validator Registration in Metagraph
    print_section("Test 4: Validator Registration in Metagraph")
    
    try:
        print(f"\n🔍 Loading validator wallet: {VALIDATOR_WALLET_NAME}/{VALIDATOR_HOTKEY}...")
        validator_wallet = bt.wallet(name=VALIDATOR_WALLET_NAME, hotkey=VALIDATOR_HOTKEY)
        validator_hotkey_address = str(validator_wallet.hotkey.ss58_address)
        print(f"   Validator hotkey: {validator_hotkey_address}")
        
        validator_uid = find_validator_in_metagraph(metagraph, validator_hotkey_address)
        
        if validator_uid is not None:
            print_result("Validator Registered", True, f"Validator found at UID {validator_uid}")
        else:
            print_result("Validator Registered", False, "Validator not found in metagraph")
            print("\n⚠️  WARNING: Validator is not registered in the metagraph!")
            
    except Exception as e:
        print_result("Validator Registration Check", False, str(e))
        import traceback
        traceback.print_exc()
    
    # Test 5: Synapse Communication Test
    print_section("Test 5: Synapse Communication Test")
    
    # Try synapse test if miner is registered (even if external port check failed)
    # Bittensor uses metagraph axon info which should work even behind NAT
    if miner_uid is not None:
        try:
            print(f"\n🔍 Testing synapse communication with miner UID {miner_uid}...")
            
            # Create dendrite for validator
            validator_dendrite = bt.dendrite(wallet=validator_wallet)
            miner_axon = metagraph.axons[miner_uid]
            
            # Test data
            test_data = {
                'task_type': 'transcription',
                'input_data': 'test audio data',
                'source_language': 'en'
            }
            
            print(f"   Sending test synapse to miner...")
            result = asyncio.run(test_synapse_communication(
                validator_dendrite, 
                miner_axon, 
                test_data
            ))
            
            if result['success']:
                print_result("Synapse Communication", True, 
                           f"Response received in {result['elapsed_time']:.2f}s")
                print(f"   Response: {result['response']}")
            else:
                print_result("Synapse Communication", False, result.get('error', 'Unknown error'))
                print(f"   Error: {result.get('error', 'No response')}")
                print(f"   Elapsed time: {result.get('elapsed_time', 0):.2f}s")
                
        except Exception as e:
            print_result("Synapse Communication", False, str(e))
            import traceback
            traceback.print_exc()
    else:
        print("⏭️  Skipping synapse test (miner not registered or port not open)")
    
    # Summary
    print_section("Test Summary & Recommendations")
    
    issues = []
    if not miner_port_open:
        issues.append("❌ Miner port is not accessible")
    if miner_uid is None:
        issues.append("❌ Miner is not registered in metagraph")
    if validator_uid is None:
        issues.append("❌ Validator is not registered in metagraph")
    if miner_uid is not None:
        miner_axon = metagraph.axons[miner_uid]
        external_ip = getattr(miner_axon, 'ip_external', None)
        external_port = getattr(miner_axon, 'port_external', None)
        if miner_axon.ip != MINER_IP and (not external_ip or external_ip != MINER_IP):
            issues.append("❌ Miner IP mismatch in metagraph")
        if miner_axon.port != MINER_PORT and (not external_port or external_port != MINER_PORT):
            issues.append("❌ Miner port mismatch in metagraph")
    
    if issues:
        print("\n⚠️  Issues Found:")
        for issue in issues:
            print(f"   {issue}")
        
        print("\n💡 Recommendations:")
        if not miner_port_open:
            print("   1. Check if miner is running:")
            print(f"      python neurons/miner.py --netuid {NETUID} --subtensor.network {NETWORK} \\")
            print(f"        --wallet.name {MINER_WALLET_NAME} --wallet.hotkey {MINER_HOTKEY} \\")
            print(f"        --axon.ip {MINER_IP} --axon.port {MINER_PORT} \\")
            print(f"        --axon.external_ip {MINER_IP} --axon.external_port {MINER_PORT}")
            print("   2. Check firewall rules (allow port 8091)")
            print("   3. Verify port forwarding if behind NAT")
        
        if miner_uid is None:
            print("   4. Ensure miner has registered on-chain")
            print("   5. Verify wallet name and hotkey are correct")
            print("   6. Check miner logs for registration errors")
        
        if miner_uid is not None:
            miner_axon = metagraph.axons[miner_uid]
            external_ip = getattr(miner_axon, 'ip_external', None)
            external_port = getattr(miner_axon, 'port_external', None)
            ip_mismatch = miner_axon.ip != MINER_IP and (not external_ip or external_ip != MINER_IP)
            port_mismatch = miner_axon.port != MINER_PORT and (not external_port or external_port != MINER_PORT)
            if ip_mismatch or port_mismatch:
                print("   7. Restart miner with correct IP/port to update metagraph")
                print("   8. Wait for metagraph to sync (may take a few blocks)")
    else:
        print("\n✅ All basic checks passed!")
        print("   If validator still cannot find miner, check:")
        print("   - Validator's get_available_miners() logic")
        print("   - Validator's metagraph sync")
        print("   - Miner's axon.is_serving status")
    
    print("\n" + "=" * 80)
    print(f"Test completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

