"""
Bittensor Metagraph Verification Module
Verifies user credentials against Bittensor network metagraphs
"""

import bittensor as bt
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class BittensorVerifier:
    """Verify Bittensor credentials against metagraph"""
    
    # Network configurations
    NETWORKS = {
        'test': {
            'network': 'test',
            'netuid': 292,
            'chain_endpoint': 'wss://test.finney.opentensor.ai:443'
        },
        'finney': {
            'network': 'finney',
            'netuid': 49,
            'chain_endpoint': 'wss://entrypoint-finney.opentensor.ai:443'
        }
    }
    
    def __init__(self):
        self.subtensors = {}
        self.metagraphs = {}
    
    def _get_subtensor(self, network: str):
        """Get or create subtensor for network"""
        if network not in self.subtensors:
            config = self.NETWORKS.get(network)
            if not config:
                raise ValueError(f"Unknown network: {network}")
            
            subtensor = bt.subtensor(network=config['network'])
            self.subtensors[network] = subtensor
        
        return self.subtensors[network]
    
    def _get_metagraph(self, network: str):
        """Get or create metagraph for network"""
        if network not in self.metagraphs:
            config = self.NETWORKS.get(network)
            if not config:
                raise ValueError(f"Unknown network: {network}")
            
            subtensor = self._get_subtensor(network)
            metagraph = subtensor.metagraph(netuid=config['netuid'])
            self.metagraphs[network] = metagraph
        
        return self.metagraphs[network]
    
    def verify_credentials(
        self, 
        hotkey: str, 
        coldkey_address: str, 
        uid: int, 
        network: str,
        netuid: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify user credentials against Bittensor metagraph
        
        Returns:
            (is_valid, error_message)
        """
        try:
            # Validate network
            if network not in self.NETWORKS:
                return False, f"Invalid network: {network}. Must be 'test' or 'finney'"
            
            config = self.NETWORKS[network]
            
            # Validate netuid matches network
            if netuid != config['netuid']:
                return False, f"Invalid netuid: {netuid} for network {network}. Expected {config['netuid']}"
            
            # Get metagraph
            metagraph = self._get_metagraph(network)
            
            # Verify UID is within valid range
            if uid < 0 or uid >= metagraph.n:
                return False, f"Invalid UID: {uid}. Must be between 0 and {metagraph.n - 1}"
            
            # Get hotkey from metagraph at UID
            metagraph_hotkey = metagraph.hotkeys[uid]
            
            # Verify hotkey matches
            if metagraph_hotkey != hotkey:
                return False, f"Hotkey mismatch. Metagraph has {metagraph_hotkey} at UID {uid}, provided {hotkey}"
            
            # Get coldkey from metagraph
            metagraph_coldkey = metagraph.coldkeys[uid]
            
            # Verify coldkey address matches
            if metagraph_coldkey != coldkey_address:
                return False, f"Coldkey mismatch. Metagraph has {metagraph_coldkey} at UID {uid}, provided {coldkey_address}"
            
            # All checks passed
            logger.info(f"✅ Credentials verified for UID {uid} on {network} network")
            return True, None
            
        except Exception as e:
            logger.error(f"❌ Error verifying credentials: {e}")
            return False, f"Verification error: {str(e)}"
    
    def get_miner_info(self, network: str, uid: int) -> Optional[Dict]:
        """Get miner information from metagraph"""
        try:
            metagraph = self._get_metagraph(network)
            
            if uid < 0 or uid >= metagraph.n:
                return None
            
            return {
                'uid': uid,
                'hotkey': metagraph.hotkeys[uid],
                'coldkey': metagraph.coldkeys[uid],
                'stake': float(metagraph.S[uid]) if hasattr(metagraph, 'S') else 0.0,
                'is_serving': metagraph.axons[uid].is_serving if hasattr(metagraph, 'axons') else False,
                'ip': metagraph.axons[uid].ip if hasattr(metagraph, 'axons') else None,
                'port': metagraph.axons[uid].port if hasattr(metagraph, 'axons') else None
            }
            
        except Exception as e:
            logger.error(f"Error getting miner info: {e}")
            return None

