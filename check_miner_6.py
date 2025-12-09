#!/usr/bin/env python3
"""
Script to check external IP and port of miner UID 6 on testnet 292
"""

import bittensor as bt
import sys

def check_miner_6():
    """Check external IP and port of miner UID 6 on testnet 292"""
    
    try:
        # Connect to testnet
        print("🔗 Connecting to Bittensor testnet...")
        subtensor = bt.subtensor(network="test")
        
        # Get metagraph for netuid 292
        print("📊 Loading metagraph for netuid 292...")
        metagraph = subtensor.metagraph(netuid=292)
        
        # Check if UID 6 exists
        total_miners = len(metagraph.hotkeys)
        print(f"📈 Total miners in network: {total_miners}")
        
        if 6 >= total_miners:
            print(f"❌ Error: UID 6 does not exist. Network only has UIDs 0-{total_miners-1}")
            return
        
        # Get miner UID 6 information
        uid = 6
        axon = metagraph.axons[uid]
        hotkey = metagraph.hotkeys[uid]
        stake = metagraph.S[uid]
        is_serving = axon.is_serving
        
        print(f"\n{'='*60}")
        print(f"🔍 Miner UID 6 Information")
        print(f"{'='*60}")
        print(f"Hotkey: {hotkey}")
        print(f"Stake: {stake:,.0f} TAO")
        print(f"Is Serving: {is_serving}")
        print(f"\n📍 IP/Port Information:")
        
        # Get regular IP and port
        regular_ip = axon.ip
        regular_port = axon.port
        
        # Convert IP from int to string if needed
        if isinstance(regular_ip, int):
            regular_ip_str = f"{regular_ip >> 24}.{(regular_ip >> 16) & 255}.{(regular_ip >> 8) & 255}.{regular_ip & 255}"
        else:
            regular_ip_str = str(regular_ip)
        
        print(f"  Regular IP: {regular_ip_str}")
        print(f"  Regular Port: {regular_port}")
        
        # Get external IP and port
        external_ip = getattr(axon, 'external_ip', None)
        external_port = getattr(axon, 'external_port', None)
        
        if external_ip:
            if isinstance(external_ip, int):
                external_ip_str = f"{external_ip >> 24}.{(external_ip >> 16) & 255}.{(external_ip >> 8) & 255}.{external_ip & 255}"
            else:
                external_ip_str = str(external_ip)
            print(f"  External IP: {external_ip_str}")
        else:
            print(f"  External IP: None (not set)")
        
        if external_port:
            print(f"  External Port: {external_port}")
        else:
            print(f"  External Port: None (not set)")
        
        print(f"\n{'='*60}")
        print(f"📋 Summary:")
        print(f"{'='*60}")
        
        if external_ip and external_port:
            print(f"✅ External IP/Port: {external_ip_str}:{external_port}")
            print(f"   (This is what validators should use for connection)")
        else:
            print(f"⚠️  External IP/Port not set")
            print(f"   Using regular IP/Port: {regular_ip_str}:{regular_port}")
            print(f"   (Miner should use --axon.external_ip and --axon.external_port flags)")
        
        print(f"\n🔗 Connection String:")
        if external_ip and external_port:
            print(f"   {external_ip_str}:{external_port}")
        else:
            print(f"   {regular_ip_str}:{regular_port}")
        
        print(f"\n✅ Check complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    check_miner_6()

