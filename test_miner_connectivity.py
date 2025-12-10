#!/usr/bin/env python3
"""
Test script to verify miner connectivity and axon status
"""

import bittensor as bt
import sys
import asyncio
from template.protocol import AudioTask
import base64

async def test_miner_connectivity():
    """Test connectivity to miner UID 6"""
    
    try:
        # Connect to testnet
        print("🔗 Connecting to Bittensor testnet...")
        subtensor = bt.subtensor(network="test")
        
        # Get metagraph for netuid 292
        print("📊 Loading metagraph for netuid 292...")
        metagraph = subtensor.metagraph(netuid=292)
        
        # Get miner UID 6
        uid = 6
        if uid >= len(metagraph.hotkeys):
            print(f"❌ Error: UID {uid} does not exist")
            return
        
        axon = metagraph.axons[uid]
        hotkey = metagraph.hotkeys[uid]
        
        print(f"\n{'='*60}")
        print(f"🔍 Testing Miner UID {uid}")
        print(f"{'='*60}")
        print(f"Hotkey: {hotkey}")
        print(f"Is Serving: {axon.is_serving}")
        
        # Get IP and port
        ip = axon.ip
        port = axon.port
        if isinstance(ip, int):
            ip = f"{ip >> 24}.{(ip >> 16) & 255}.{(ip >> 8) & 255}.{ip & 255}"
        
        print(f"IP: {ip}")
        print(f"Port: {port}")
        
        # Create wallet for dendrite
        print(f"\n🔧 Creating dendrite...")
        wallet = bt.wallet(name="validator", hotkey="default")
        dendrite = bt.dendrite(wallet=wallet)
        
        # Create handshake task
        print(f"\n🤝 Creating handshake task...")
        test_text = "This is a test for handshake verification."
        handshake_task = AudioTask(
            task_type="summarization",
            input_data=base64.b64encode(test_text.encode('utf-8')).decode('utf-8'),
            language="en"
        )
        
        # Try to connect
        print(f"\n🔗 Attempting handshake with {ip}:{port}...")
        print(f"   Timeout: 15 seconds")
        
        try:
            responses = await asyncio.wait_for(
                dendrite(
                    axons=[axon],
                    synapse=handshake_task,
                    deserialize=False,
                    timeout=15
                ),
                timeout=20
            )
            
            if responses and len(responses) > 0:
                response = responses[0]
                
                # Get status code
                status_code = 200
                if hasattr(response, 'dendrite') and hasattr(response.dendrite, 'status_code'):
                    status_code = response.dendrite.status_code
                
                print(f"\n✅ Handshake SUCCESS!")
                print(f"   Status Code: {status_code}")
                
                if hasattr(response, 'output_data') and response.output_data:
                    try:
                        decoded = base64.b64decode(response.output_data.encode('utf-8'))
                        print(f"   Response: {decoded.decode('utf-8', errors='ignore')[:100]}")
                    except:
                        print(f"   Response: {response.output_data[:100]}")
            else:
                print(f"\n❌ Handshake FAILED: No response")
                
        except asyncio.TimeoutError:
            print(f"\n❌ Handshake FAILED: Timeout after 20 seconds")
            print(f"   This suggests the miner is not accessible at {ip}:{port}")
            print(f"   Possible causes:")
            print(f"   - Firewall blocking port {port}")
            print(f"   - Miner axon not started")
            print(f"   - Network connectivity issues")
        except Exception as e:
            print(f"\n❌ Handshake FAILED: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n{'='*60}")
        print(f"✅ Test complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_miner_connectivity())

