"""
Cache Manager for Validator
Provides efficient caching for metagraph, miner metrics, and other frequently accessed data.
Refreshes cache based on block progression to ensure data freshness.
"""

import time
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
import threading
import bittensor as bt


class CacheManager:
    """Manages caching for validator to reduce server load and improve performance"""
    
    def __init__(self, refresh_interval_blocks: int = 1):
        """
        Initialize cache manager
        
        Args:
            refresh_interval_blocks: Number of blocks before cache refresh (default: 1 = every block)
        """
        self.refresh_interval_blocks = refresh_interval_blocks
        self.last_refresh_block = 0
        
        # Cache storage
        self.metagraph_cache: Optional[Dict] = None
        self.miner_metrics_cache: Dict[int, Dict] = {}
        self.miner_hotkeys_cache: Dict[int, str] = {}
        self.miner_coldkeys_cache: Dict[int, str] = {}
        
        # Cache timestamps
        self.metagraph_cache_time: Optional[float] = None
        self.metrics_cache_time: Dict[int, float] = {}
        self.hotkeys_cache_time: Dict[int, float] = {}
        
        # Cache TTL (time-to-live) in seconds
        self.metagraph_ttl = 300  # 5 minutes
        self.metrics_ttl = 60  # 1 minute
        self.hotkeys_ttl = 600  # 10 minutes (hotkeys don't change often)
        
        # Thread lock for thread-safe operations
        self.lock = threading.Lock()
        
        bt.logging.info(f"✅ CacheManager initialized (refresh every {refresh_interval_blocks} blocks)")
    
    def should_refresh_cache(self, current_block: int) -> bool:
        """
        Check if cache should be refreshed based on block progression
        
        Args:
            current_block: Current block number
            
        Returns:
            True if cache should be refreshed
        """
        blocks_since_refresh = current_block - self.last_refresh_block
        return blocks_since_refresh >= self.refresh_interval_blocks
    
    def refresh_cache(self, current_block: int):
        """
        Mark cache as refreshed for current block
        
        Args:
            current_block: Current block number
        """
        self.last_refresh_block = current_block
        bt.logging.debug(f"🔄 Cache refresh marked for block {current_block}")
    
    def get_cached_metagraph(self, current_block: int) -> Optional[Dict]:
        """
        Get cached metagraph data if still valid
        
        Args:
            current_block: Current block number
            
        Returns:
            Cached metagraph data or None if cache is stale
        """
        with self.lock:
            if self.metagraph_cache is None:
                return None
            
            # Check if cache should be refreshed based on blocks
            if self.should_refresh_cache(current_block):
                bt.logging.debug(f"🔄 Metagraph cache expired (block {current_block})")
                return None
            
            # Check TTL
            if self.metagraph_cache_time:
                age = time.time() - self.metagraph_cache_time
                if age > self.metagraph_ttl:
                    bt.logging.debug(f"🔄 Metagraph cache expired (age: {age:.1f}s)")
                    return None
            
            return self.metagraph_cache
    
    def set_metagraph_cache(self, metagraph_data: Dict, current_block: int):
        """
        Cache metagraph data
        
        Args:
            metagraph_data: Metagraph data to cache
            current_block: Current block number
        """
        with self.lock:
            self.metagraph_cache = metagraph_data
            self.metagraph_cache_time = time.time()
            self.refresh_cache(current_block)
            bt.logging.debug(f"💾 Metagraph cached for block {current_block}")
    
    def get_cached_hotkey(self, miner_uid: int, current_block: int) -> Optional[str]:
        """
        Get cached hotkey for a miner
        
        Args:
            miner_uid: Miner UID
            current_block: Current block number
            
        Returns:
            Cached hotkey or None if not cached or stale
        """
        with self.lock:
            if miner_uid not in self.miner_hotkeys_cache:
                return None
            
            # Check if cache should be refreshed
            if self.should_refresh_cache(current_block):
                return None
            
            # Check TTL
            if miner_uid in self.hotkeys_cache_time:
                age = time.time() - self.hotkeys_cache_time[miner_uid]
                if age > self.hotkeys_ttl:
                    return None
            
            return self.miner_hotkeys_cache[miner_uid]
    
    def set_hotkey_cache(self, miner_uid: int, hotkey: str, current_block: int):
        """
        Cache hotkey for a miner
        
        Args:
            miner_uid: Miner UID
            hotkey: Hotkey to cache
            current_block: Current block number
        """
        with self.lock:
            self.miner_hotkeys_cache[miner_uid] = hotkey
            self.hotkeys_cache_time[miner_uid] = time.time()
            bt.logging.debug(f"💾 Hotkey cached for miner {miner_uid}")
    
    def get_cached_metrics(self, miner_uid: int, current_block: int) -> Optional[Dict]:
        """
        Get cached metrics for a miner
        
        Args:
            miner_uid: Miner UID
            current_block: Current block number
            
        Returns:
            Cached metrics or None if not cached or stale
        """
        with self.lock:
            if miner_uid not in self.miner_metrics_cache:
                return None
            
            # Check if cache should be refreshed
            if self.should_refresh_cache(current_block):
                return None
            
            # Check TTL
            if miner_uid in self.metrics_cache_time:
                age = time.time() - self.metrics_cache_time[miner_uid]
                if age > self.metrics_ttl:
                    return None
            
            return self.miner_metrics_cache[miner_uid]
    
    def set_metrics_cache(self, miner_uid: int, metrics: Dict, current_block: int):
        """
        Cache metrics for a miner
        
        Args:
            miner_uid: Miner UID
            metrics: Metrics to cache
            current_block: Current block number
        """
        with self.lock:
            self.miner_metrics_cache[miner_uid] = metrics
            self.metrics_cache_time[miner_uid] = time.time()
            bt.logging.debug(f"💾 Metrics cached for miner {miner_uid}")
    
    def clear_metrics_cache(self, miner_uid: Optional[int] = None):
        """
        Clear metrics cache for a specific miner or all miners
        
        Args:
            miner_uid: Miner UID to clear (None = clear all)
        """
        with self.lock:
            if miner_uid is None:
                self.miner_metrics_cache.clear()
                self.metrics_cache_time.clear()
                bt.logging.debug("🗑️ All metrics cache cleared")
            else:
                self.miner_metrics_cache.pop(miner_uid, None)
                self.metrics_cache_time.pop(miner_uid, None)
                bt.logging.debug(f"🗑️ Metrics cache cleared for miner {miner_uid}")
    
    def clear_all_cache(self):
        """Clear all caches"""
        with self.lock:
            self.metagraph_cache = None
            self.metagraph_cache_time = None
            self.miner_metrics_cache.clear()
            self.metrics_cache_time.clear()
            self.miner_hotkeys_cache.clear()
            self.hotkeys_cache_time.clear()
            bt.logging.info("🗑️ All caches cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            return {
                'metagraph_cached': self.metagraph_cache is not None,
                'metagraph_cache_age': time.time() - self.metagraph_cache_time if self.metagraph_cache_time else None,
                'miner_metrics_count': len(self.miner_metrics_cache),
                'miner_hotkeys_count': len(self.miner_hotkeys_cache),
                'last_refresh_block': self.last_refresh_block,
                'refresh_interval_blocks': self.refresh_interval_blocks
            }

