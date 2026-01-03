# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# TODO(developer): Set your name
# Copyright © 2023 <your name>

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.


import sys
import os
# Ensure we use the local template from this project, not from other projects
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
# Also add neurons directory to path for relative imports (but after project root)
_neurons_dir = os.path.dirname(os.path.abspath(__file__))
if _neurons_dir not in sys.path:
    sys.path.insert(1, _neurons_dir)  # Insert at position 1, after project root

# Load environment variables from .env file early (before other imports)
from dotenv import load_dotenv
from pathlib import Path
_env_file = Path(_project_root) / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
    print(f"✅ Loaded .env file from: {_env_file}")
else:
    load_dotenv()  # Try loading from current directory
    print(f"ℹ️ No .env file found at {_env_file}, using system environment variables")

import time
import asyncio
import requests
import json
import numpy as np
import torch
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import difflib
import os
import pickle

# Bittensor
import bittensor as bt
import httpx

# import base validator class which takes care of most of the boilerplate
from template.base.validator import BaseValidatorNeuron

# Bittensor Validator Template:

from template.protocol import AudioTask

# Import CacheManager after path setup
# Use relative import since we're in the neurons directory
try:
    from cache_manager import CacheManager
except ImportError:
    # Fallback: try absolute import if relative fails
    try:
        from neurons.cache_manager import CacheManager
    except ImportError:
        # Last resort: add project root explicitly and try again
        import sys
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
        from neurons.cache_manager import CacheManager


class Validator(BaseValidatorNeuron):
    """
    Enhanced Audio processing validator that evaluates transcription, TTS, and summarization services.
    This validator rewards miners based on speed, accuracy, and stake, prioritizing the top 10 performers.
    Features enhanced block monitoring, task evaluation tracking, and comprehensive logging.
    """

    def __init__(self, config=None):
        # Initialize critical attributes BEFORE calling parent constructor
        self.proxy_tasks_processed_this_epoch = False
        self.proxy_server_url = "https://violet-proxy-bl4w.onrender.com"  # Production proxy server URL
        self.last_miner_status_report = 0
        self.miner_status_report_interval = 100  # Report every 100 blocks (1 epoch)
        
        # Enhanced block monitoring and evaluation tracking
        self.current_epoch = 0
        self.last_evaluation_block = 0
        self.evaluation_interval = 100  # Evaluate every 100 blocks
        self.evaluated_tasks_cache = set()  # In-memory cache of evaluated tasks
        self.evaluation_history = {}  # Track evaluation history per epoch
        self.performance_metrics = {}  # Track performance metrics over time
        
        # Weight setting optimization
        self.last_weight_setting_block = 0
        self.last_weight_commit_timestamp = 0  # Track timestamp of last successful weight commit
        self.min_weight_commit_interval = 600  # Minimum 10 minutes between weight commits (Bittensor cooldown)
        self.weight_setting_interval = 100  # Set weights every 100 blocks
        self.miner_weight_history = {}  # Track weight changes over time
        
        # Enhanced logging and monitoring
        self.log_file_path = f"logs/validator/validator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.performance_log_path = f"logs/validator/performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Caching system for performance optimization
        self.cache_manager = CacheManager(refresh_interval_blocks=1)  # Refresh every block
        
        super(Validator, self).__init__(config=config)

        bt.logging.info("load_state()")
        self.load_state()

        # Ensure log directories exist (after parent constructor)
        os.makedirs("logs/validator", exist_ok=True)

        # Proxy server integration settings
        self.proxy_server_url = os.getenv('PROXY_SERVER_URL', 'https://violet-proxy-bl4w.onrender.com')
        self.enable_proxy_integration = os.getenv('ENABLE_PROXY_INTEGRATION', 'True').lower() == 'true'
        self.proxy_check_interval = int(os.getenv('PROXY_CHECK_INTERVAL', '30'))  # seconds
        
        # Load validator API key from environment variable (like HF_TOKEN)
        self.validator_api_key = os.getenv('VALIDATOR_API_KEY')
        if not self.validator_api_key:
            bt.logging.warning("⚠️  VALIDATOR_API_KEY not found in .env file. Validator endpoints will be rejected.")
            bt.logging.warning("   Add VALIDATOR_API_KEY=<your_api_key> to your .env file")
        else:
            bt.logging.info(f"✅ Validator API key loaded from .env (length: {len(self.validator_api_key)})")
        
        # Initialize proxy integration if enabled
        if self.enable_proxy_integration:
            bt.logging.info(f"🔗 Proxy server integration enabled: {self.proxy_server_url}")
            self.last_proxy_check = 0
        else:
            bt.logging.info("⚠️  Proxy server integration disabled")
        
        # Initialize miner tracker for performance monitoring and load balancing
        try:
            from template.validator.miner_tracker import MinerTracker
            self.miner_tracker = MinerTracker(self.config)
            bt.logging.info("✅ Miner tracker initialized for load balancing and performance tracking")
        except Exception as e:
            bt.logging.warning(f"⚠️  Failed to initialize miner tracker: {e}")
            self.miner_tracker = None
        
        # REMOVED: Pipeline initialization - Validator does not execute pipelines
        # self.initialize_miner_pipelines()
        
        # Initialize enhanced monitoring
        self.initialize_enhanced_monitoring()
        
        bt.logging.info("🚀 Enhanced validator initialized with comprehensive monitoring and evaluation tracking")
    
    def initialize_miner_pipelines(self):
        """Initialize pipeline manager for on-demand model loading (same as miner)"""
        try:
            bt.logging.info("🔧 Initializing pipeline manager for on-demand model loading...")
            
            # Initialize pipeline manager for dynamic model loading (same as miner)
            # Models will be loaded only when tasks are assigned
            # Use importlib to avoid any module-level side effects
            import importlib
            import sys
            
            # Check if pipeline_manager module is already imported
            if 'template.pipelines.pipeline_manager' in sys.modules:
                bt.logging.warning("⚠️ pipeline_manager module already imported - this might cause side effects")
            
            # Import the module and get the class
            pipeline_manager_module = importlib.import_module('template.pipelines.pipeline_manager')
            PipelineManager = pipeline_manager_module.PipelineManager
            
            # Create a new instance - PipelineManager.__init__ only sets up empty dicts, no model loading
            bt.logging.debug("Creating PipelineManager instance...")
            self.pipeline_manager = PipelineManager()
            bt.logging.debug("PipelineManager instance created successfully")
            
            # Verify no models were loaded
            cache_stats = self.pipeline_manager.get_cache_stats()
            if any(count > 0 for count in cache_stats.values()):
                bt.logging.warning(f"⚠️ Models were loaded during initialization! Cache stats: {cache_stats}")
            else:
                bt.logging.info("✅ Pipeline manager initialized - models will be loaded on-demand when tasks are assigned")
            
        except Exception as e:
            bt.logging.error(f"❌ Error initializing pipeline manager: {str(e)}")
            import traceback
            bt.logging.error(f"   Traceback: {traceback.format_exc()}")
    
    def initialize_enhanced_monitoring(self):
        """Initialize enhanced monitoring and tracking systems"""
        try:
            bt.logging.info("🔧 Initializing enhanced monitoring systems...")
            
            # Load existing evaluation history if available
            self.load_evaluation_history()
            
            # Initialize current epoch
            self.current_epoch = self.block // self.evaluation_interval if hasattr(self, 'block') else 0
            
            # Log initialization
            bt.logging.info(f"📊 Enhanced monitoring initialized:")
            bt.logging.info(f"   Current Block: {getattr(self, 'block', 'Unknown')}")
            bt.logging.info(f"   Current Epoch: {self.current_epoch}")
            bt.logging.info(f"   Evaluation Interval: {self.evaluation_interval} blocks")
            bt.logging.info(f"   Weight Setting Interval: {self.weight_setting_interval} blocks")
            bt.logging.info(f"   Log File: {self.log_file_path}")
            bt.logging.info(f"   Performance Log: {self.performance_log_path}")
            
        except Exception as e:
            bt.logging.error(f"❌ Error initializing enhanced monitoring: {str(e)}")
    
    def load_evaluation_history(self):
        """Load evaluation history from disk if available"""
        try:
            history_file = "logs/validator/evaluation_history.pkl"
            if os.path.exists(history_file):
                with open(history_file, 'rb') as f:
                    self.evaluation_history = pickle.load(f)
                bt.logging.info(f"📚 Loaded evaluation history: {len(self.evaluation_history)} epochs")
            else:
                self.evaluation_history = {}
                bt.logging.info("📚 No existing evaluation history found, starting fresh")
        except Exception as e:
            bt.logging.warning(f"⚠️  Could not load evaluation history: {str(e)}")
            self.evaluation_history = {}
    
    def save_evaluation_history(self):
        """Save evaluation history to disk"""
        try:
            history_file = "logs/validator/evaluation_history.pkl"
            with open(history_file, 'wb') as f:
                pickle.dump(self.evaluation_history, f)
            bt.logging.debug("💾 Evaluation history saved to disk")
        except Exception as e:
            bt.logging.warning(f"⚠️  Could not save evaluation history: {str(e)}")
    
    def should_evaluate_tasks(self) -> bool:
        """
        Determine if we should evaluate tasks based on block progression
        """
        if not hasattr(self, 'block'):
            return False
        
        # Check if enough blocks have passed since last evaluation
        blocks_since_evaluation = self.block - self.last_evaluation_block
        
        if blocks_since_evaluation >= self.evaluation_interval:
            bt.logging.info(f"🔍 Evaluation trigger: {blocks_since_evaluation} blocks since last evaluation")
            return True
        
        return False
    
    def should_set_weights(self) -> bool:
        """
        Enhanced weight setting logic with better block monitoring and evaluation tracking.
        Includes time-based cooldown to respect Bittensor's commit-reveal mechanism.
        """
        if not hasattr(self, 'block'):
            return False
        
        # Don't set weights if proxy tasks were processed this epoch
        if self.proxy_tasks_processed_this_epoch:
            bt.logging.info("🔄 Skipping weight setting - proxy tasks were processed this epoch")
            return False
        
        # Don't set weights if there are no reachable miners
        if not hasattr(self, 'reachable_miners') or not self.reachable_miners:
            bt.logging.info("🔄 Skipping weight setting - no reachable miners available")
            return False
        
        # CRITICAL FIX: Check if new evaluation occurred since last weight setting
        # Only set weights if we've evaluated new tasks
        if hasattr(self, 'last_evaluation_block') and hasattr(self, 'last_weight_setting_block'):
            if self.last_evaluation_block <= self.last_weight_setting_block:
                bt.logging.info("🔄 Skipping weight setting - no new evaluation since last weight setting")
                bt.logging.info(f"   Last evaluation block: {self.last_evaluation_block}, Last weight setting block: {self.last_weight_setting_block}")
                return False
        
        # CRITICAL FIX: Check time-based cooldown (Bittensor commit-reveal cooldown)
        if self.last_weight_commit_timestamp > 0:
            time_since_last_commit = time.time() - self.last_weight_commit_timestamp
            if time_since_last_commit < self.min_weight_commit_interval:
                bt.logging.info(f"⏳ Too soon to commit weights ({time_since_last_commit:.0f}s < {self.min_weight_commit_interval}s cooldown)")
                bt.logging.info(f"   Bittensor commit-reveal mechanism requires minimum {self.min_weight_commit_interval}s between commits")
            return False
        
        # Check if enough blocks have passed since last weight setting
        blocks_since_weight_setting = self.block - self.last_weight_setting_block
        
        if blocks_since_weight_setting >= self.weight_setting_interval:
            bt.logging.info(f"⚖️  Weight setting trigger: {blocks_since_weight_setting} blocks since last weight setting")
            bt.logging.info(f"   Time since last commit: {time.time() - self.last_weight_commit_timestamp:.0f}s (cooldown: {self.min_weight_commit_interval}s)")
            bt.logging.info(f"   New evaluation occurred: {self.last_evaluation_block > self.last_weight_setting_block}")
            
            # Reset the flag when we're about to set weights (new epoch)
            self.proxy_tasks_processed_this_epoch = False
            
            # Update tracking
            self.last_weight_setting_block = self.block
            self.current_epoch = self.block // self.evaluation_interval
            
            return True
        
        return False
    
    def log_block_status(self):
        """Log current block status and monitoring information"""
        try:
            if hasattr(self, 'block'):
                bt.logging.info("=" * 80)
                bt.logging.info(f"📊 BLOCK STATUS UPDATE - Block {self.block}")
                bt.logging.info(f"   Current Epoch: {self.current_epoch}")
                bt.logging.info(f"   Blocks Since Last Evaluation: {self.block - self.last_evaluation_block}")
                bt.logging.info(f"   Blocks Since Last Weight Setting: {self.block - self.last_weight_setting_block}")
                bt.logging.info(f"   Evaluation Interval: {self.evaluation_interval} blocks")
                bt.logging.info(f"   Weight Setting Interval: {self.weight_setting_interval} blocks")
                
                # Log miner status
                if hasattr(self, 'reachable_miners'):
                    bt.logging.info(f"   Reachable Miners: {len(self.reachable_miners)}")
                    if self.reachable_miners:
                        top_miners = sorted(self.reachable_miners, key=lambda x: self.metagraph.S[x], reverse=True)[:3]
                        bt.logging.info(f"   Top Miners by Stake: {top_miners}")
                
                # Log evaluation status
                if self.evaluated_tasks_cache:
                    bt.logging.info(f"   Tasks Evaluated This Epoch: {len(self.evaluated_tasks_cache)}")
                
                bt.logging.info("=" * 80)
                
        except Exception as e:
            bt.logging.error(f"❌ Error logging block status: {str(e)}")

    async def check_miner_connectivity(self):
        """
        Perform on-chain handshake with miners to verify they are active and responsive.
        Only miners that successfully respond to on-chain queries are considered active.
        This follows the pattern used by serious Bittensor subnets.
        
        IMPORTANT: Always uses CURRENT metagraph data - no hardcoded values.
        Checks ALL miners every iteration to catch new miners joining the network.
        """
        try:
            # ALWAYS use current metagraph data - resync if needed
            # The metagraph is updated in the forward() loop, but we ensure we have latest
            total_miners = len(self.metagraph.hotkeys)
            serving_miners = 0
            active_miners = []  # Only miners that respond to on-chain queries
            
            bt.logging.info(f"🔍 Performing on-chain handshake with serving miners (checking {total_miners} total miners)...")
            
            # Check EACH miner in the metagraph - this ensures we catch new miners
            for uid in range(total_miners):
                # ALWAYS get fresh data from metagraph - no caching, no hardcoding
                axon = self.metagraph.axons[uid]
                hotkey = self.metagraph.hotkeys[uid]
                stake = self.metagraph.S[uid]
                is_serving = axon.is_serving
                
                if not is_serving:
                    continue  # Skip non-serving miners
                
                    serving_miners += 1
                    
                # Get IP and port information from CURRENT metagraph data
                # IMPORTANT: Always use fresh data from metagraph - no caching, no hardcoding
                # The metagraph is synced every step in the run loop, so this is always current
                
                # For logging purposes, get both regular and external IP/port
                regular_ip = axon.ip
                regular_port = axon.port
                external_ip = getattr(axon, 'external_ip', None)
                external_port = getattr(axon, 'external_port', None)
                
                # Convert IPs to strings for logging
                if isinstance(regular_ip, int):
                    regular_ip_str = f"{regular_ip >> 24}.{(regular_ip >> 16) & 255}.{(regular_ip >> 8) & 255}.{regular_ip & 255}"
                else:
                    regular_ip_str = str(regular_ip)
                
                external_ip_str = None
                if external_ip:
                    if isinstance(external_ip, int):
                        external_ip_str = f"{external_ip >> 24}.{(external_ip >> 16) & 255}.{(external_ip >> 8) & 255}.{external_ip & 255}"
                    else:
                        external_ip_str = str(external_ip)
                
                # Use external_ip/external_port for logging if available, otherwise use regular ip/port
                # This matches what Bittensor will use for connection
                ip = external_ip_str if external_ip_str else regular_ip_str
                port = external_port if external_port and external_port != 0 else regular_port
                
                # IMPORTANT: We pass the axon object directly to dendrite
                # Bittensor's dendrite automatically uses the correct IP/port from the axon
                # The axon object from metagraph contains all on-chain registered information
                # including external_ip/external_port if the miner registered with those flags
                # We don't need to manually select IP/port - Bittensor handles it
                
                # Perform on-chain handshake query using summarization task
                try:
                    # Create a simple handshake/test task - use summarization for consistency
                    from template.protocol import AudioTask
                    # Use a small text for summarization handshake
                    test_text = "This is a test for handshake verification."
                    import base64
                    handshake_task = AudioTask(
                        task_type="summarization",
                        input_data=base64.b64encode(test_text.encode('utf-8')).decode('utf-8'),
                        language="en"
                    )
                        
                    # Perform on-chain query using dendrite (this is the on-chain handshake)
                    # IMPORTANT: We pass the axon object directly from CURRENT metagraph
                    # Bittensor's dendrite will automatically use the correct IP/port from the axon
                    # The axon object contains all on-chain registered information (including external_ip/external_port)
                    # NOTE: Only log successful handshakes to reduce log noise
                    
                    # Use asyncio.wait_for to ensure we don't hang indefinitely
                    # This matches the pattern used in working Bittensor subnets
                    try:
                        responses = await asyncio.wait_for(
                            self.dendrite(
                                axons=[axon],  # Use CURRENT metagraph axon - Bittensor handles IP/port automatically
                                synapse=handshake_task,
                                deserialize=False,  # Don't deserialize for handshake
                                timeout=15  # Increased to 15 seconds for handshake (was 10)
                            ),
                            timeout=20  # Outer timeout to prevent hanging
                        )
                    except asyncio.TimeoutError:
                        # Timeout occurred - miner not responding (silently skip, no logging)
                        continue  # Skip to next miner
                    
                    # Check if miner responded successfully
                    if responses and len(responses) > 0:
                        response = responses[0]
                        
                        # Get status code from dendrite response
                        if hasattr(response, 'dendrite') and hasattr(response.dendrite, 'status_code'):
                            status_code = response.dendrite.status_code
                        else:
                            # If response exists, consider it successful (miner is online)
                            status_code = 200
                        
                        # Only consider miner active if we get a valid response (200, 400, or 500)
                        # 200 = success, 400/500 = error but miner is online and responding
                        if status_code in [200, 400, 500]:
                            active_miners.append(uid)
                            # ONLY log successful handshakes - this reduces log noise
                            bt.logging.info(
                                f"✅ UID {uid:3d} | {ip}:{port} | "
                                f"Stake: {stake:,.0f} TAO | "
                                f"On-chain handshake: SUCCESS (Status: {status_code})"
                            )
                        # Failed handshakes are silently skipped (no logging to reduce noise)
                    # No response is silently skipped (no logging to reduce noise)
                        
                except asyncio.TimeoutError:
                    # Already handled above, but catch here too for safety (silently skip)
                    continue  # Skip to next miner
                except Exception as e:
                    # Miner did not respond to on-chain query - not active (silently skip)
                    # Only log unexpected errors (not timeouts or connection errors)
                    error_msg = str(e)
                    if "Timeout" not in error_msg and "408" not in error_msg and "Connect" not in error_msg:
                        # Only log unexpected errors, not common connection failures
                        bt.logging.debug(f"⚠️ Unexpected error handshaking with UID {uid:3d}: {error_msg[:50]}...")
                    continue  # Skip to next miner
            
            # Summary of on-chain handshake results
            bt.logging.info("─" * 60)
            if active_miners:
                # Sort by stake for display
                top_miners = sorted(active_miners, key=lambda x: self.metagraph.S[x], reverse=True)[:5]
                bt.logging.info(
                    f"🎯 On-Chain Handshake Results: "
                    f"{len(active_miners)}/{serving_miners} miners active "
                    f"({(len(active_miners)/serving_miners*100):.1f}% success rate)"
                )
                bt.logging.info(f"   Top active miners by stake: {top_miners}")
                
                # Store active miners (only those that passed on-chain handshake)
                self.reachable_miners = active_miners
            else:
                bt.logging.warning(
                    f"⚠️  On-chain handshake: No active miners found "
                    f"({serving_miners} serving but none responded)"
                )
                self.reachable_miners = []
            
            bt.logging.info("─" * 60)
            
        except Exception as e:
            bt.logging.error(f"❌ Error performing on-chain handshake: {str(e)}")
            import traceback
            bt.logging.debug(f"   Traceback: {traceback.format_exc()}")
            self.reachable_miners = []
    
    async def forward(self):
        """
        Enhanced validator forward pass with comprehensive monitoring and evaluation tracking.
        Consists of:
        - Block status monitoring and logging
        - Proxy server task checking
        - Task evaluation and weight setting
        - Performance tracking and reporting
        - Periodic maintenance and cleanup
        """
        try:
            # Get current block for cache management
            current_block = self.block if hasattr(self, 'block') else 0
            
            # Refresh cache if needed (every block)
            if hasattr(self, 'cache_manager'):
                if self.cache_manager.should_refresh_cache(current_block):
                    bt.logging.debug(f"🔄 Refreshing cache for block {current_block}")
                    self.cache_manager.refresh_cache(current_block)
                    # Clear stale metrics cache to force refresh
                    self.cache_manager.clear_metrics_cache()
            
            # Log block status every 10 blocks for monitoring
            if hasattr(self, 'block') and self.step % 10 == 0:
                self.log_block_status()
            
            # Perform periodic maintenance
            self.periodic_maintenance()
            
            # Check if we should evaluate tasks based on block progression
            if self.should_evaluate_tasks():
                bt.logging.info(f"🔍 Evaluation trigger activated at block {self.block}")
                await self.trigger_task_evaluation()
            
            # ALWAYS check miner connectivity and report status to proxy (regardless of proxy tasks)
            # This ensures proxy server always has current miner status
            await self.check_miner_connectivity()
            
            # Report miner status to proxy server EVERY forward pass
            # This ensures proxy always has up-to-date miner information
            if hasattr(self, 'reachable_miners') and self.reachable_miners:
                await self.report_miner_status_to_proxy()
            
            # Check proxy server for tasks if integration is enabled
            proxy_tasks_processed = False
            if self.enable_proxy_integration:
                proxy_tasks_processed = await self.check_proxy_server_tasks()
            
            # Only run the standard forward pass if no proxy tasks were processed
            # This prevents weight setting when we're evaluating proxy tasks
            if not proxy_tasks_processed:
                return await self._run_standard_forward()
            else:
                bt.logging.info("🔄 Proxy tasks processed, skipping standard forward pass to prevent weight setting")
                
                # Run the enhanced task evaluation and weight setting process
                await self.evaluate_completed_tasks_and_set_weights()
                return None
                
        except Exception as e:
            bt.logging.error(f"❌ Error in enhanced forward pass: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    async def trigger_task_evaluation(self):
        """Trigger task evaluation when conditions are met"""
        try:
            bt.logging.info("🚀 Triggering task evaluation...")
            
            # Update evaluation tracking
            self.last_evaluation_block = self.block
            
            # Check if we have completed tasks to evaluate
            if self.enable_proxy_integration:
                await self.evaluate_completed_tasks_and_set_weights()
            else:
                bt.logging.info("⚠️  Proxy integration disabled, skipping task evaluation")
                
        except Exception as e:
            bt.logging.error(f"❌ Error triggering task evaluation: {str(e)}")
    
    async def _run_standard_forward(self):
        """Standard forward pass implementation with enhanced monitoring"""
        try:
            # Note: Miner connectivity check and status reporting are now done in forward() 
            # before this method is called, to ensure they happen every forward pass
            
            # Check if we have any reachable miners
            if not hasattr(self, 'reachable_miners') or not self.reachable_miners:
                bt.logging.warning("No reachable miners available. Skipping this round.")
                return
            
            # Log standard forward pass execution
            bt.logging.info("🔄 Running standard forward pass with enhanced monitoring...")
            
            # Update performance metrics
            self.update_performance_metrics('standard_forward', success=True)
            
            return None
            
        except Exception as e:
            bt.logging.error(f"❌ Error in standard forward pass: {str(e)}")
            self.update_performance_metrics('standard_forward', success=False, error=str(e))
            return None
    
    def update_performance_metrics(self, operation: str, success: bool, error: str = None, **kwargs):
        """Update performance metrics for monitoring and analysis"""
        try:
            if operation not in self.performance_metrics:
                self.performance_metrics[operation] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'failed_calls': 0,
                    'errors': [],
                    'last_call': None,
                    'avg_response_time': 0.0,
                    'response_times': []
                }
            
            metrics = self.performance_metrics[operation]
            metrics['total_calls'] += 1
            metrics['last_call'] = datetime.now().isoformat()
            
            if success:
                metrics['successful_calls'] += 1
            else:
                metrics['failed_calls'] += 1
                if error:
                    metrics['errors'].append({
                        'timestamp': datetime.now().isoformat(),
                        'error': error
                    })
            
            # Keep only last 100 errors to prevent memory bloat
            if len(metrics['errors']) > 100:
                metrics['errors'] = metrics['errors'][-100:]
            
            # Log performance update
            success_rate = (metrics['successful_calls'] / metrics['total_calls']) * 100
            bt.logging.debug(f"📊 Performance update for {operation}: {success_rate:.1f}% success rate")
            
        except Exception as e:
            bt.logging.warning(f"⚠️  Error updating performance metrics: {str(e)}")
    
    def get_performance_summary(self) -> Dict:
        """Get a summary of current performance metrics"""
        try:
            summary = {
                'total_operations': 0,
                'overall_success_rate': 0.0,
                'operation_breakdown': {},
                'recent_errors': [],
                'timestamp': datetime.now().isoformat()
            }
            
            total_successful = 0
            total_calls = 0
            
            for operation, metrics in self.performance_metrics.items():
                total_calls += metrics['total_calls']
                total_successful += metrics['successful_calls']
                
                success_rate = (metrics['successful_calls'] / metrics['total_calls']) * 100 if metrics['total_calls'] > 0 else 0
                
                summary['operation_breakdown'][operation] = {
                    'total_calls': metrics['total_calls'],
                    'success_rate': success_rate,
                    'last_call': metrics['last_call']
                }
                
                # Collect recent errors
                if metrics['errors']:
                    summary['recent_errors'].extend(metrics['errors'][-5:])  # Last 5 errors per operation
            
            if total_calls > 0:
                summary['overall_success_rate'] = (total_successful / total_calls) * 100
            
            summary['total_operations'] = total_calls
            
            return summary
            
        except Exception as e:
            bt.logging.error(f"❌ Error generating performance summary: {str(e)}")
            return {'error': str(e)}
    
    async def check_proxy_server_tasks(self):
        """Get tasks ready for evaluation from proxy server, excluding tasks already seen by this validator"""
        try:
            validator_uid = getattr(self, 'uid', None)
            validator_identifier = f"validator_{validator_uid}" if validator_uid else f"validator_{self.wallet.hotkey.ss58_address}"
            
            bt.logging.info(f"🔍 Checking proxy server for tasks (Validator: {validator_identifier})...")
            bt.logging.info(f"   Each validator sees ALL tasks, but only evaluates tasks it hasn't seen yet")
            
            # Get tasks ready for evaluation (status='done') - filtering is done in get_tasks_ready_for_evaluation
            pending_tasks = await self.get_tasks_ready_for_evaluation()
            
            if pending_tasks:
                bt.logging.info(f"📋 Found {len(pending_tasks)} new tasks for this validator to evaluate")
                await self.process_proxy_tasks(pending_tasks)
                return True
            else:
                bt.logging.info(f"📭 No new tasks for this validator to evaluate")
                return False
            
        except Exception as e:
            bt.logging.error(f"❌ Error checking proxy server tasks: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def get_tasks_ready_for_evaluation(self):
        """
        Get tasks ready for evaluation from proxy server.
        Returns ALL tasks with status='done' or 'completed', but filters out tasks
        already seen by THIS validator (not other validators).
        Each validator sees all tasks, but only evaluates ones it hasn't seen yet.
        """
        try:
            validator_uid = getattr(self, 'uid', None)
            validator_identifier = f"validator_{validator_uid}" if validator_uid else f"validator_{self.wallet.hotkey.ss58_address}"
            
            bt.logging.info(f"🔍 Fetching ALL tasks from proxy server (Validator: {validator_identifier})...")
            bt.logging.info(f"   Each validator sees ALL tasks, but filters out ones it has already seen")
            
            # Get ALL tasks from proxy server (no filtering by validators_seen on server side)
            all_tasks = await self.get_proxy_pending_tasks()
            
            if not all_tasks:
                bt.logging.info(f"📭 No tasks available from proxy server")
                return []
            
            # Filter for only 'done' or 'completed' tasks
            done_tasks = [task for task in all_tasks if task.get('status') in ['done', 'completed']]
            bt.logging.info(f"   Found {len(done_tasks)} tasks with status 'done' or 'completed'")
            
            # Filter out tasks already seen by THIS validator only (not other validators)
            new_tasks = []
            for task in done_tasks:
                task_id = task.get('task_id')
                validators_seen = task.get('validators_seen', [])
                
                # Check if THIS validator has already seen this task
                if validator_identifier in validators_seen or (validator_uid and str(validator_uid) in validators_seen):
                    bt.logging.debug(f"⏭️  Skipping task {task_id} - already seen by this validator ({validator_identifier})")
                    continue
                
                new_tasks.append(task)
            
            if new_tasks:
                bt.logging.info(f"✅ Found {len(new_tasks)} new tasks for this validator to evaluate")
                bt.logging.info(f"   Filtered out {len(done_tasks) - len(new_tasks)} tasks already seen by this validator")
            else:
                bt.logging.info(f"📭 No new tasks for this validator - all {len(done_tasks)} done tasks have been seen by this validator")
            
            return new_tasks
            
        except Exception as e:
            bt.logging.error(f"❌ Error getting tasks ready for evaluation: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_auth_headers(self) -> dict:
        """Get authentication headers with API key"""
        headers = {}
        if self.validator_api_key:
            headers["X-API-Key"] = self.validator_api_key
        return headers
    
    async def get_proxy_pending_tasks(self):
        """
        Get tasks ready for evaluation from proxy server.
        Returns ALL tasks - filtering by validators_seen happens in get_tasks_ready_for_evaluation.
        Includes retry logic with exponential backoff for better reliability.
        """
        validator_uid = getattr(self, 'uid', None)
        validator_identifier = f"validator_{validator_uid}" if validator_uid else f"validator_{self.wallet.hotkey.ss58_address}"
        
        bt.logging.info(f"🔍 Fetching ALL tasks from proxy server (Validator: {validator_identifier})...")
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_timeout = 60  # Increased from 10 to 60 seconds
        headers = self._get_auth_headers()
        
        for attempt in range(max_retries):
            try:
                timeout = base_timeout * (attempt + 1)  # Increase timeout with each retry
                bt.logging.debug(f"   Attempt {attempt + 1}/{max_retries} with {timeout}s timeout...")
                
                response = requests.get(
                    f"{self.proxy_server_url}/api/v1/validator/tasks", 
                    headers=headers, 
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    all_tasks = data.get('tasks', [])
                    
                    bt.logging.info(f"📋 Received {len(all_tasks)} total tasks from proxy server")
                    bt.logging.info(f"   ✅ Proxy server returns ALL tasks - validator will filter based on its own validators_seen")
                    
                    return all_tasks
                else:
                    bt.logging.warning(f"⚠️  Proxy server returned status {response.status_code}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        bt.logging.info(f"   Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        return []
                        
            except requests.exceptions.Timeout as e:
                timeout_seconds = base_timeout * (attempt + 1)
                bt.logging.warning(f"⏰ Proxy server request timed out after {timeout_seconds}s (attempt {attempt + 1}/{max_retries})")
                bt.logging.info(f"   The proxy server is taking longer than expected to respond. This may be due to high load or network issues.")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    next_timeout = base_timeout * (attempt + 2)
                    bt.logging.info(f"   ⏳ Retrying in {wait_time}s with increased timeout ({next_timeout}s)...")
                    await asyncio.sleep(wait_time)
                else:
                    bt.logging.error(f"❌ Connection failed: Proxy server did not respond within {timeout_seconds}s after {max_retries} attempts")
                    bt.logging.info(f"   💡 Possible causes: Proxy server is down, network issues, or server overload")
                    return []
                    
            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    timeout_seconds = base_timeout * (attempt + 1)
                    bt.logging.warning(f"⏰ Request timeout after {timeout_seconds}s (attempt {attempt + 1}/{max_retries})")
                else:
                    bt.logging.warning(f"⚠️  Network error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    bt.logging.info(f"   ⏳ Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    bt.logging.error(f"❌ Failed to connect to proxy server after {max_retries} attempts")
                    bt.logging.info(f"   💡 Check your network connection and verify the proxy server URL is correct")
                    return []
        
        return []
    
    async def process_proxy_tasks(self, pending_tasks):
        """Process pending tasks from proxy server"""
        try:
            bt.logging.info(f"🔄 Processing {len(pending_tasks)} tasks from proxy server...")
            
            for task_data in pending_tasks:
                task_id = task_data.get('task_id')
                task_type = task_data.get('task_type')
                language = task_data.get('language')
                input_data = task_data.get('input_data')
                
                bt.logging.info(f"📝 Processing task {task_id}: {task_type} ({language})")
                
                # Process the task using the existing forward logic
                result = await self.process_single_proxy_task(task_data)
                
                if result:
                    # Send result back to proxy server
                    await self.submit_result_to_proxy(task_id, result)
                
        except Exception as e:
            bt.logging.error(f"❌ Error processing proxy tasks: {str(e)}")
    
    async def process_single_proxy_task(self, task_data):
        """Process a single task from proxy server"""
        try:
            task_id = task_data.get('task_id')
            task_type = task_data.get('task_type')
            language = task_data.get('language', 'en')  # Default to English if not specified
            input_data = task_data.get('input_data', '')  # Default to empty string if not specified
            
            # Validate required fields
            if not task_type:
                bt.logging.error(f"❌ Task {task_id} missing task_type")
                return None
            
            if not input_data:
                bt.logging.error(f"❌ Task {task_id} missing input_data")
                return None
            
            bt.logging.info(f"🎯 Processing proxy task: {task_type} in {language}")
            
            # Create AudioTask synapse for this task
            from template.protocol import AudioTask
            
            synapse = AudioTask(
                task_type=task_type,
                input_data=input_data,
                language=language
            )
            
            # Use miner tracker for intelligent miner selection with load balancing
            if self.miner_tracker:
                # Register miners if not already done
                for uid in self.get_available_miners():
                    if uid < len(self.metagraph.hotkeys):
                        hotkey = self.metagraph.hotkeys[uid]
                        stake = self.metagraph.S[uid]
                        self.miner_tracker.register_miner(uid, hotkey, stake)
                
                # Select 3 miners using intelligent load balancing
                miner_uids = self.miner_tracker.select_miners_for_task(task_type, required_count=3)
                bt.logging.info(f"🎯 Intelligent miner selection: {miner_uids}")
            else:
                # Fallback to stake-based selection
                available_uids = self.get_available_miners()
                if not available_uids:
                    bt.logging.warning("⚠️  No available miners found")
                    return None
                
                miner_uids = sorted(available_uids, key=lambda x: self.metagraph.S[x], reverse=True)[:3]
                bt.logging.info(f"🎯 Fallback miner selection: {miner_uids}")
            
            # Query miners
            responses = await self.dendrite(
                axons=[self.metagraph.axons[uid] for uid in miner_uids],
                synapse=synapse,
                deserialize=True,
            )
            
            # Evaluate responses and find best one
            best_response = await self.evaluate_miner_responses(
                responses, miner_uids, task_type, input_data, language
            )
            
            if best_response:
                bt.logging.info(f"✅ Best response found from miner {best_response['miner_uid']}")
                return best_response
            else:
                bt.logging.warning("⚠️  No valid responses from miners")
                return None
                
        except Exception as e:
            bt.logging.error(f"❌ Error processing single proxy task: {str(e)}")
            return None
    
    async def evaluate_miner_responses(self, responses, miner_uids, task_type, input_data, language):
        """Evaluate miner responses and find the best one"""
        try:
            best_response = None
            best_score = 0
            
            bt.logging.info(f"🔍 Evaluating {len(responses)} miner responses...")
            
            for i, response in enumerate(responses):
                if i >= len(miner_uids):
                    continue
                    
                uid = miner_uids[i]
                if not response:
                    bt.logging.warning(f"⚠️  No response from miner {uid}")
                    continue
                
                if not hasattr(response, 'output_data') or not response.output_data:
                    bt.logging.warning(f"⚠️  No output data from miner {uid}")
                    continue
                
                # Calculate scores
                accuracy_score = await self.calculate_accuracy_score(response, task_type, input_data, language)
                speed_score = self.calculate_speed_score(response.processing_time if hasattr(response, 'processing_time') else 10.0, task_type)
                
                # Combined score (accuracy 70%, speed 30%)
                combined_score = (accuracy_score * 0.7) + (speed_score * 0.3)
                
                bt.logging.info(f"📊 Miner {uid} scores - Accuracy: {accuracy_score:.4f}, Speed: {speed_score:.4f}, Combined: {combined_score:.4f}")
                
                # Update miner tracker with performance data
                if self.miner_tracker:
                    processing_time = getattr(response, 'processing_time', 10.0)
                    success = combined_score > 0.5  # Consider response successful if score > 0.5
                    self.miner_tracker.update_task_result(uid, task_type, success, processing_time)
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_response = {
                        'output_data': response.output_data,
                        'processing_time': getattr(response, 'processing_time', 10.0),
                        'miner_uid': uid,
                        'accuracy_score': accuracy_score,
                        'speed_score': speed_score,
                        'combined_score': combined_score
                    }
                    
                    bt.logging.info(f"🏆 New best response from miner {uid} with score {combined_score:.4f}")
            
            return best_response
            
        except Exception as e:
            bt.logging.error(f"❌ Error evaluating responses: {str(e)}")
            return None
    
    async def calculate_accuracy_score(self, response, task_type, input_data, language):
        """Calculate accuracy score for a response"""
        try:
            if task_type == "transcription":
                # For transcription, we'll use a placeholder score for now
                # In a real implementation, you'd compare with ground truth
                return 0.85  # Placeholder score
            elif task_type == "summarization":
                return 0.80  # Placeholder score
            elif task_type == "tts":
                return 0.75  # Placeholder score
            else:
                return 0.5
        except Exception as e:
            bt.logging.error(f"❌ Error calculating accuracy score: {str(e)}")
            return 0.0
    
    def calculate_speed_score(self, processing_time: float, task_type: str) -> float:
        """Calculate speed score based on processing time and task type"""
        try:
            # Define optimal processing times for different task types
            optimal_times = {
                'transcription': 2.0,  # 2 seconds optimal
                'tts': 3.0,            # 3 seconds optimal  
                'summarization': 5.0   # 5 seconds optimal
            }
            
            optimal_time = optimal_times.get(task_type, 5.0)
            
            # Score based on how close to optimal time
            if processing_time <= optimal_time:
                # Faster than optimal = perfect score
                return 1.0
            elif processing_time <= optimal_time * 2:
                # Within 2x optimal = good score
                return 0.8
            elif processing_time <= optimal_time * 5:
                # Within 5x optimal = acceptable score
                return 0.6
            else:
                # Too slow = poor score
                return 0.3
                
        except Exception as e:
            bt.logging.error(f"❌ Error calculating speed score: {str(e)}")
            return 0.5

    def calculate_quality_score(self, miner_response: Dict, task_type: str) -> float:
        """Calculate quality score based on response structure and completeness"""
        try:
            quality_score = 0.0
            
            # Check if response has required fields
            response_data = miner_response.get('response_data', {})
            
            if task_type == 'transcription':
                # Check for transcript field
                if 'output_data' in response_data:
                    output_data = response_data['output_data']
                    if isinstance(output_data, str):
                        # Parse the string output data
                        import ast
                        try:
                            parsed = ast.literal_eval(output_data)
                            if 'transcript' in parsed and parsed['transcript']:
                                quality_score += 0.4
                            if 'confidence' in parsed:
                                quality_score += 0.3
                            if 'language' in parsed:
                                quality_score += 0.3
                        except:
                            quality_score += 0.2  # Partial credit for having output_data
                    else:
                        # Direct dict format
                        if 'transcript' in output_data and output_data['transcript']:
                            quality_score += 0.4
                        if 'confidence' in output_data:
                            quality_score += 0.3
                        if 'language' in output_data:
                            quality_score += 0.3
                            
            elif task_type == 'tts':
                # Check for audio data
                if 'output_data' in response_data:
                    output_data = response_data['output_data']
                    if isinstance(output_data, str):
                        try:
                            parsed = ast.literal_eval(output_data)
                            if 'audio_data' in parsed:
                                quality_score += 0.7
                            if 'duration' in parsed:
                                quality_score += 0.3
                        except:
                            quality_score += 0.3
                    else:
                        if 'audio_data' in output_data:
                            quality_score += 0.7
                        if 'duration' in output_data:
                            quality_score += 0.3
                            
            elif task_type == 'summarization':
                # Check for summary
                if 'output_data' in response_data:
                    output_data = response_data['output_data']
                    if isinstance(output_data, str):
                        try:
                            parsed = ast.literal_eval(output_data)
                            if 'summary' in parsed and parsed['summary']:
                                quality_score += 0.6
                            if 'key_points' in parsed:
                                quality_score += 0.4
                        except:
                            quality_score += 0.3
                    else:
                        if 'summary' in output_data and output_data['summary']:
                            quality_score += 0.6
                        if 'key_points' in output_data:
                            quality_score += 0.4
            
            # Check for processing metrics
            if 'processing_time' in miner_response:
                quality_score += 0.1
            if 'accuracy_score' in miner_response:
                quality_score += 0.1
            if 'speed_score' in miner_response:
                quality_score += 0.1
                
            return min(quality_score, 1.0)  # Cap at 1.0
            
        except Exception as e:
            bt.logging.error(f"❌ Error calculating quality score: {str(e)}")
            return 0.5
    
    def get_available_miners(self):
        """Get list of available miners"""
        try:
            available_miners = []
            for uid in range(len(self.metagraph.hotkeys)):
                if self.metagraph.axons[uid].is_serving:
                    available_miners.append(uid)
            return available_miners
        except Exception as e:
            bt.logging.error(f"❌ Error getting available miners: {str(e)}")
            return []
    
    async def submit_result_to_proxy(self, task_id, result):
        """Submit task result back to proxy server"""
        try:
            data = {
                'task_id': task_id,
                'result': result['output_data'],
                'processing_time': result['processing_time'],
                'miner_uid': result['miner_uid'],
                'accuracy_score': result['accuracy_score'],
                'speed_score': result['speed_score']
            }
            
            # Save miner metrics periodically
            if self.miner_tracker:
                self.miner_tracker.save_metrics()
            
            headers = self._get_auth_headers()
            response = requests.post(
                f"{self.proxy_server_url}/api/v1/validator/submit_result",
                headers=headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                bt.logging.info(f"✅ Result submitted to proxy server for task {task_id}")
            else:
                bt.logging.warning(f"⚠️  Failed to submit result to proxy server: {response.status_code}")
                
        except Exception as e:
            bt.logging.error(f"❌ Error submitting result to proxy server: {str(e)}")

    async def report_miner_status_to_proxy(self):
        """
        Report ONLY active miners (those that passed on-chain handshake) to proxy server.
        This ensures proxy server only knows about miners that are actually online and responsive.
        """
        try:
            # Check if we have validator API key
            if not self.validator_api_key:
                bt.logging.warning("⚠️ VALIDATOR_API_KEY not set - cannot report miners to proxy")
                return
            
            # Only report miners that passed on-chain handshake (are in reachable_miners)
            if not hasattr(self, 'reachable_miners') or not self.reachable_miners:
                bt.logging.debug("🔄 No active miners to report (none passed on-chain handshake)")
                return
            
            active_miners = self.reachable_miners  # These are miners that passed on-chain handshake
            
            bt.logging.info(
                f"📊 Reporting {len(active_miners)} active miner(s) to proxy server "
                f"(passed on-chain handshake)..."
            )
            
            miner_statuses = []
            
            for uid in active_miners:
                try:
                    # Get miner information from metagraph
                    axon = self.metagraph.axons[uid]
                    hotkey = self.metagraph.hotkeys[uid]
                    stake = self.metagraph.S[uid]
                    
                    # Get IP information - use getattr() to safely access attributes that may not exist
                    ip = axon.ip
                    port = axon.port
                    external_ip = getattr(axon, 'external_ip', None)
                    external_port = getattr(axon, 'external_port', None)
                    
                    # Convert IP from int to string if needed
                    if isinstance(ip, int):
                        ip = f"{ip >> 24}.{(ip >> 16) & 255}.{(ip >> 8) & 255}.{ip & 255}"
                    
                    # Convert external_ip if it exists and is an int
                    if external_ip and isinstance(external_ip, int):
                        external_ip = f"{external_ip >> 24}.{(external_ip >> 16) & 255}.{(external_ip >> 8) & 255}.{external_ip & 255}"
                    elif external_ip and isinstance(external_ip, str):
                        # Already a string, use as is
                        pass
                    else:
                        # external_ip is None or invalid, set to None
                        external_ip = None
                    
                    # Calculate performance score based on recent interactions
                    performance_score = self.calculate_miner_performance_score(uid)
                    
                    # Get current load (estimate based on recent activity)
                    current_load = self.estimate_miner_current_load(uid)
                    
                    # Task type specialization (based on recent performance)
                    task_type_specialization = self.get_miner_task_specialization(uid)
                    
                    miner_status = {
                        'uid': uid,
                        'hotkey': hotkey,
                        'ip': ip,
                        'port': port,
                        'external_ip': external_ip,
                        'external_port': external_port,
                        'is_serving': axon.is_serving,
                        'stake': float(stake),
                        'performance_score': performance_score,
                        'current_load': current_load,
                        'max_capacity': 5,  # Default capacity
                        'last_seen': datetime.now().isoformat(),
                        'task_type_specialization': task_type_specialization
                    }
                    
                    miner_statuses.append(miner_status)
                    
                except Exception as e:
                    error_msg = str(e)
                    bt.logging.warning(f"⚠️ Error getting status for miner {uid}: {error_msg}")
                    import traceback
                    bt.logging.debug(f"   Traceback: {traceback.format_exc()}")
                    continue
            
            if miner_statuses:
                # Send to proxy server
                success = await self.send_miner_status_to_proxy(miner_statuses)
                
                if success:
                    bt.logging.info(f"✅ Reported {len(miner_statuses)} miner statuses to proxy")
                    self.last_miner_status_report = self.step
                else:
                    bt.logging.warning("⚠️ Failed to report miner status to proxy")
            else:
                bt.logging.debug("🔄 No miner statuses to report")
                
        except Exception as e:
            bt.logging.error(f"❌ Error reporting miner status: {str(e)}")
    
    async def send_miner_status_to_proxy(self, miner_statuses: List[Dict]) -> bool:
        """Send miner status to proxy server via HTTP API"""
        try:
            import json
            proxy_endpoint = f"{self.proxy_server_url}/api/v1/validators/miner-status"
            
            # Validate we have API key
            if not self.validator_api_key:
                bt.logging.error("❌ VALIDATOR_API_KEY not set - cannot send miner status to proxy")
                return False
            
            # Proxy server expects Form data, not JSON
            data = {
                'validator_uid': str(self.uid),
                'miner_statuses': json.dumps(miner_statuses),  # JSON string for Form field
                'epoch': str(self.step // 100)
            }
            
            bt.logging.info(f"📤 Sending {len(miner_statuses)} miner status(es) to proxy server...")
            bt.logging.debug(f"   Endpoint: {proxy_endpoint}")
            bt.logging.debug(f"   Validator UID: {self.uid}")
            bt.logging.debug(f"   Epoch: {self.step // 100}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = self._get_auth_headers()
                bt.logging.debug(f"   API Key present: {bool(headers.get('X-API-Key'))}")
                
                response = await client.post(proxy_endpoint, headers=headers, data=data)
                
                if response.status_code == 200:
                    bt.logging.info(f"✅ Successfully sent miner status to proxy server")
                    try:
                        result = response.json()
                        bt.logging.debug(f"   Response: {result}")
                    except:
                        pass
                    return True
                else:
                    bt.logging.error(f"❌ Proxy returned status {response.status_code}: {response.text}")
                    return False
                    
        except httpx.TimeoutException:
            bt.logging.error("⏰ Timeout connecting to proxy server (30s timeout)")
            bt.logging.info("   💡 The proxy server did not respond in time. This may be due to:")
            bt.logging.info("      - High server load")
            bt.logging.info("      - Network connectivity issues")
            bt.logging.info("      - Proxy server temporarily unavailable")
            return False
        except httpx.ConnectError as e:
            bt.logging.error(f"🔌 Connection error to proxy server: {e}")
            return False
        except Exception as e:
            bt.logging.error(f"❌ Error sending miner status to proxy: {str(e)}")
            import traceback
            bt.logging.debug(f"   Traceback: {traceback.format_exc()}")
            return False
    
    def calculate_miner_performance_score(self, uid: int) -> float:
        """Calculate miner performance score based on recent interactions"""
        try:
            # This is a simplified performance calculation
            # In a real implementation, you'd track actual task completion rates
            
            # Base score from stake (higher stake = higher base score)
            stake = self.metagraph.S[uid]
            max_stake = self.metagraph.S.max()
            base_score = float(stake / max_stake) if max_stake > 0 else 0.5
            
            # Add some randomness for now (replace with actual performance tracking)
            import random
            performance_bonus = random.uniform(-0.1, 0.1)
            
            final_score = max(0.1, min(1.0, base_score + performance_bonus))
            return final_score
            
        except Exception as e:
            bt.logging.debug(f"⚠️ Error calculating performance for miner {uid}: {str(e)[:30]}...")
            return 0.5
    
    def estimate_miner_current_load(self, uid: int) -> int:
        """Estimate miner current load (simplified implementation)"""
        try:
            # This is a simplified load estimation
            # In a real implementation, you'd track actual task assignments
            
            # Random load between 0-3 for now
            import random
            return random.randint(0, 3)
            
        except Exception as e:
            bt.logging.debug(f"⚠️ Error estimating load for miner {uid}: {str(e)[:30]}...")
            return 0
    
    def get_miner_task_specialization(self, uid: int) -> Dict:
        """Get miner task type specialization (simplified implementation)"""
        try:
            # This is a simplified specialization
            # In a real implementation, you'd track actual task performance by type
            
            # Mock specialization data
            return {
                'transcription': {
                    'total': 10,
                    'successful': 9,
                    'avg_time': 2.5,
                    'success_rate': 0.9
                },
                'tts': {
                    'total': 8,
                    'successful': 7,
                    'avg_time': 3.1,
                    'success_rate': 0.875
                }
            }
            
        except Exception as e:
            bt.logging.debug(f"⚠️ Error getting specialization for miner {uid}: {str(e)[:30]}...")
            return {}

    async def evaluate_completed_tasks_and_set_weights(self):
        """
        Enhanced main method for evaluating completed tasks and setting miner weights.
        This method:
        1. Tests proxy server connection
        2. Reports current miner status to proxy server
        3. Fetches completed tasks from proxy server
        4. Filters out already evaluated tasks
        5. Executes each task as a miner would
        6. Compares validator results with miner results
        7. Calculates scores and ranks for each miner
        8. Sets weights based on cumulative performance
        9. Generates comprehensive performance reports
        10. Tracks evaluation history and performance metrics
        """
        try:
            start_time = time.time()
            bt.logging.info("🚀 Starting enhanced task evaluation and weight setting process...")
            
            # Update performance metrics
            self.update_performance_metrics('evaluation_start', success=True)
            
            # First test proxy server connection
            bt.logging.info("🔍 Testing proxy server connection...")
            if not await self.test_proxy_server_connection():
                bt.logging.error("❌ Failed to connect to proxy server, aborting evaluation")
                self.update_performance_metrics('evaluation_start', success=False, error="Proxy server connection failed")
                return
            
            bt.logging.info("✅ Proxy server connection test successful, proceeding with evaluation")
            
            # CRITICAL FIX: Report current miner status to proxy server
            bt.logging.info("📊 Reporting current miner status to proxy server...")
            try:
                await self.report_miner_status_to_proxy()
                bt.logging.info("✅ Miner status reported to proxy server")
            except Exception as e:
                bt.logging.warning(f"⚠️ Failed to report miner status: {e}")
            
            # Fetch completed tasks from proxy server
            completed_tasks = await self.fetch_completed_tasks_from_proxy()
            if not completed_tasks:
                bt.logging.info("📭 No completed tasks found for evaluation")
                return
            
            bt.logging.info(f"📋 Found {len(completed_tasks)} completed tasks for evaluation")
            
            # Filter out tasks that have already been evaluated by this validator
            bt.logging.info("🔍 Filtering out already evaluated tasks...")
            new_tasks = await self.filter_already_evaluated_tasks(completed_tasks)
            
            if not new_tasks:
                bt.logging.info("📭 All tasks have already been evaluated by this validator")
                return
            
            bt.logging.info(f"📋 Proceeding with {len(new_tasks)} new tasks for evaluation")
            
            # Log summary of tasks to be evaluated
            bt.logging.info("=" * 80)
            bt.logging.info("📊 TASKS SELECTED FOR EVALUATION")
            bt.logging.info("=" * 80)
            
            # Count tasks by type and status
            task_type_counts = {}
            status_counts = {}
            miner_response_counts = []
            
            for task in new_tasks:
                task_type = task.get('task_type', 'unknown')
                task_status = task.get('status', 'unknown')
                miner_responses = task.get('miner_responses', [])
                
                task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
                status_counts[task_status] = status_counts.get(task_status, 0) + 1
                miner_response_counts.append(len(miner_responses))
            
            bt.logging.info(f"📋 Task Type Breakdown:")
            for task_type, count in task_type_counts.items():
                bt.logging.info(f"   {task_type.capitalize()}: {count} tasks")
            
            bt.logging.info(f"\n📊 Status Breakdown:")
            for status, count in status_counts.items():
                bt.logging.info(f"   {status}: {count} tasks")
            
            if miner_response_counts:
                avg_responses = sum(miner_response_counts) / len(miner_response_counts)
                min_responses = min(miner_response_counts)
                max_responses = max(miner_response_counts)
                bt.logging.info(f"\n👥 Miner Response Statistics:")
                bt.logging.info(f"   Average responses per task: {avg_responses:.1f}")
                bt.logging.info(f"   Minimum responses: {min_responses}")
                bt.logging.info(f"   Maximum responses: {max_responses}")
            
            bt.logging.info("=" * 80)
            
            # Initialize miner performance tracking
            miner_performance = {}
            validator_performance = {}  # Track validator's own performance
            
            # Process each completed task
            for task_index, task in enumerate(new_tasks, 1):
                task_id = task.get('task_id')
                task_type = task.get('task_type')
                task_status = task.get('status', 'unknown')
                miner_responses = task.get('miner_responses', [])
                
                # CRITICAL VALIDATION 1: Task status must be 'done' or 'completed'
                if task_status not in ['done', 'completed']:
                    bt.logging.warning(f"⚠️ Task {task_id} has status '{task_status}', not 'done' or 'completed'. Skipping evaluation.")
                    continue
                
                # CRITICAL VALIDATION 2: Task must have at least one miner response
                if not miner_responses:
                    bt.logging.warning(f"⚠️ Task {task_id} has no miner responses - skipping reward evaluation")
                    bt.logging.info("=" * 80)
                    continue
                
                # CRITICAL VALIDATION 3: Task must be at least 1 hour old
                try:
                    from datetime import datetime, timezone
                    import dateutil.parser
                    
                    created_at_str = task.get('created_at')
                    if created_at_str:
                        if isinstance(created_at_str, str):
                            created_at = dateutil.parser.parse(created_at_str)
                        else:
                            created_at = created_at_str
                        
                        # Ensure timezone-aware
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                        
                        now = datetime.now(timezone.utc)
                        age_seconds = (now - created_at).total_seconds()
                        age_hours = age_seconds / 3600
                        
                        if age_hours < 1.0:
                            bt.logging.warning(f"⚠️ Task {task_id} is only {age_hours:.2f} hours old (minimum 1 hour required) - skipping reward evaluation")
                            bt.logging.info("=" * 80)
                            continue
                        
                        bt.logging.info(f"   ✅ Task age: {age_hours:.2f} hours (meets 1-hour requirement)")
                    else:
                        bt.logging.warning(f"⚠️ Task {task_id} missing created_at timestamp - cannot verify age")
                        # Allow to proceed but log warning
                except Exception as e:
                    bt.logging.warning(f"⚠️ Error checking task age: {e} - allowing task to proceed")
                
                # Enhanced task logging with progress tracking
                bt.logging.info("=" * 80)
                bt.logging.info(f"🔍 EVALUATING TASK {task_index}/{len(new_tasks)}: {task_id}")
                bt.logging.info(f"📋 Task Details:")
                bt.logging.info(f"   Type: {task_type}")
                bt.logging.info(f"   Status: {task_status} ✅ (Confirmed done/completed)")
                bt.logging.info(f"   Language: {task.get('language', 'en')}")
                bt.logging.info(f"   Created: {task.get('created_at', 'N/A')}")
                bt.logging.info(f"   Completed: {task.get('completed_at', 'N/A')}")
                bt.logging.info(f"   Miner Responses: {len(miner_responses)}")
                
                # Validate that responses are actually valid (have required fields)
                valid_responses = []
                for response in miner_responses:
                    miner_uid = response.get('miner_uid')
                    response_data = response.get('response', {})
                    
                    # Handle nested response structure: response['response']['response_data']['output_data']
                    # The actual output might be nested deeper
                    actual_output_data = None
                    if isinstance(response_data, dict):
                        # First check top level
                        if 'output_data' in response_data:
                            actual_output_data = response_data['output_data']
                        elif 'response_data' in response_data:
                            # Check nested response_data
                            nested_data = response_data['response_data']
                            if isinstance(nested_data, dict):
                                if 'output_data' in nested_data:
                                    actual_output_data = nested_data['output_data']
                                elif any(key in nested_data for key in [
                                    'transcript', 'audio_data', 'summary', 'translation', 
                                    'result', 'output', 'audio_file'
                                ]):
                                    # Nested data itself contains output fields
                                    actual_output_data = nested_data
                                else:
                                    # Use nested_data itself if it has output fields
                                    actual_output_data = nested_data
                        else:
                            # Check for direct output fields
                            actual_output_data = response_data
                    
                    # Check if response has actual output data
                    has_output = False
                    if actual_output_data:
                        if isinstance(actual_output_data, dict):
                            # Check for common output fields (including nested output_data)
                            if 'output_data' in actual_output_data:
                                # output_data is nested, check its contents
                                nested_output = actual_output_data['output_data']
                                if isinstance(nested_output, dict):
                                    has_output = any(key in nested_output for key in [
                                        'transcript', 'audio_data', 'summary', 'translation', 
                                        'result', 'output', 'audio_file', 'translated_text'
                                    ])
                                else:
                                    has_output = bool(nested_output)
                            else:
                                # Check for direct output fields
                                has_output = any(key in actual_output_data for key in [
                                    'transcript', 'audio_data', 'summary', 'translation', 
                                    'result', 'output', 'audio_file', 'translated_text'
                                ])
                        elif actual_output_data:  # Non-empty response
                            has_output = True
                    
                    if miner_uid is not None and has_output:
                        valid_responses.append(response)
                    else:
                        bt.logging.warning(f"   ⚠️ Invalid response from miner {miner_uid}: missing output data")
                        bt.logging.debug(f"      Response structure: {list(response.keys()) if isinstance(response, dict) else 'not a dict'}")
                        if isinstance(response_data, dict):
                            bt.logging.debug(f"      Response data keys: {list(response_data.keys())}")
                
                if not valid_responses:
                    bt.logging.warning(f"⚠️ Task {task_id} has no valid miner responses with output data - skipping reward evaluation")
                    bt.logging.info("=" * 80)
                    continue
                
                # Update miner_responses to only include valid ones
                miner_responses = valid_responses
                bt.logging.info(f"   ✅ Validated {len(miner_responses)} valid responses out of {len(task.get('miner_responses', []))} total")
                
                # Log input data summary
                input_data = task.get('input_data')
                if input_data:
                    if task_type == 'transcription':
                        bt.logging.info(f"   Input: Audio data ({len(input_data)} chars)")
                    elif task_type == 'tts':
                        bt.logging.info(f"   Input: Text data ({len(input_data)} chars)")
                    elif task_type == 'summarization':
                        bt.logging.info(f"   Input: Text data ({len(input_data)} chars)")
                    else:
                        bt.logging.info(f"   Input: {type(input_data).__name__} data")
                
                # Log miner response summary for this task
                bt.logging.info(f"📊 Miner Response Summary:")
                miner_summary = []
                for i, response in enumerate(miner_responses):
                    miner_uid = response.get('miner_uid')
                    # Extract fields from nested structure: response['response'] contains the miner's payload
                    nested_response = response.get('response', {})
                    if isinstance(nested_response, str):
                        # If it's a JSON string, parse it
                        try:
                            import json
                            nested_response = json.loads(nested_response)
                        except:
                            nested_response = {}
                    
                    # Try to get processing_time from nested response first, then top level
                    processing_time = nested_response.get('processing_time') or response.get('processing_time', 0)
                    accuracy_score = nested_response.get('accuracy_score') or response.get('accuracy_score', 0)
                    speed_score = nested_response.get('speed_score') or response.get('speed_score', 0)
                    
                    miner_summary.append(f"UID{miner_uid}({processing_time:.2f}s,{accuracy_score:.3f},{speed_score:.3f})")
                    bt.logging.info(f"      Miner {i+1}: UID {miner_uid}")
                    bt.logging.info(f"         Processing Time: {processing_time:.3f}s")
                    bt.logging.info(f"         Accuracy Score: {accuracy_score:.3f}")
                    bt.logging.info(f"         Speed Score: {speed_score:.3f}")
                    bt.logging.info(f"         Submitted: {response.get('submitted_at', 'N/A')}")
                
                bt.logging.info(f"   Summary: {', '.join(miner_summary)}")
                
                # Additional validation for completed task structure
                bt.logging.info(f"🔍 Validating completed task structure...")
                validation_passed = True
                
                # Check if all miner responses have required fields
                for i, response in enumerate(miner_responses):
                    miner_uid = response.get('miner_uid')
                    if miner_uid is None:
                        bt.logging.warning(f"⚠️ Miner response {i+1} missing miner_uid")
                        validation_passed = False
                    
                    # Extract nested response for field extraction
                    nested_response = response.get('response', {})
                    if isinstance(nested_response, str):
                        try:
                            import json
                            nested_response = json.loads(nested_response)
                        except:
                            nested_response = {}
                    
                    # CRITICAL FIX: Make processing_time optional (some miners might not provide it)
                    # Check both nested and top-level
                    processing_time = nested_response.get('processing_time') or response.get('processing_time')
                    if processing_time is None:
                        bt.logging.warning(f"⚠️ Miner response {i+1} missing processing_time, using default")
                        # Set a default processing time in both places for consistency
                        processing_time = 10.0
                        if isinstance(nested_response, dict):
                            nested_response['processing_time'] = 10.0
                        response['processing_time'] = 10.0
                    else:
                        # Ensure it's set in both places for consistency
                        if isinstance(nested_response, dict):
                            nested_response['processing_time'] = processing_time
                        response['processing_time'] = processing_time
                    
                    # CRITICAL FIX: Make submitted_at optional (some miners might not provide it)
                    if response.get('submitted_at') is None:
                        bt.logging.warning(f"⚠️ Miner response {i+1} missing submitted_at, using current time")
                        # Set a default submission time
                        response['submitted_at'] = datetime.now().isoformat()
                
                if not validation_passed:
                    bt.logging.error(f"❌ Task {task_id} failed validation. Skipping evaluation.")
                    bt.logging.info("=" * 80)
                    continue
                
                bt.logging.info(f"✅ Task structure validation passed")

                # Additional validation: Check if task has the required input data
                bt.logging.info(f"🔍 VALIDATING TASK INPUT DATA:")
                input_data_available = False
                
                # Check multiple possible sources for input data
                if task.get('input_data'):
                    bt.logging.info(f"   ✅ input_data field found")
                    input_data_available = True
                elif task.get('input_text') and isinstance(task.get('input_text'), dict):
                    if task['input_text'].get('text'):
                        bt.logging.info(f"   ✅ input_text.text field found")
                        input_data_available = True
                elif task.get('input_file_id'):
                    bt.logging.info(f"   ✅ input_file_id field found")
                    input_data_available = True
                elif task.get('input_file'):
                    input_file = task.get('input_file', {})
                    if isinstance(input_file, dict):
                        if input_file.get('content') or input_file.get('file_id'):
                            bt.logging.info(f"   ✅ input_file object with content/file_id found")
                            input_data_available = True
                        else:
                            bt.logging.warning(f"   ⚠️ input_file object found but no content/file_id")
                    else:
                        bt.logging.info(f"   ✅ input_file as direct data found")
                        input_data_available = True
                
                if not input_data_available:
                    bt.logging.error(f"❌ Task {task_id} missing required input data - cannot execute")
                    bt.logging.error(f"   Available fields: {list(task.keys())}")
                    bt.logging.error(f"   Task data preview: {str(task)[:500]}...")
                    bt.logging.info("=" * 80)
                    continue
                
                bt.logging.info(f"✅ Task input data validation passed")

                # Validator does not execute tasks - only evaluates miner responses
                # Calculate scores based on miner response quality and metrics
                bt.logging.info(f"📊 CALCULATING MINER SCORES:")
                task_scores = await self.calculate_task_scores(
                    task_id, task_type, None, miner_responses
                )
                
                if not task_scores:
                    bt.logging.warning(f"⚠️ No valid scores calculated for task {task_id}")
                    bt.logging.info("=" * 80)
                    continue
                
                # CRITICAL: Filter out invalid miners before selecting top miners
                # Only reward miners with valid responses
                valid_miner_scores = {}
                for miner_uid, score in task_scores.items():
                    # Verify miner is in valid_responses (has valid output)
                    miner_in_valid_responses = any(
                        r.get('miner_uid') == miner_uid 
                        for r in miner_responses
                    )
                    if miner_in_valid_responses and score > 0:
                        valid_miner_scores[miner_uid] = score
                    else:
                        bt.logging.warning(f"   ⚠️ Skipping invalid miner {miner_uid} (no valid response or score=0)")
                
                if not valid_miner_scores:
                    bt.logging.warning(f"⚠️ No valid miners to reward for task {task_id}")
                    bt.logging.info("=" * 80)
                    continue
                
                # Select top 10 VALID miners for this task based on performance
                top_miners = await self.select_top_miners_for_task(valid_miner_scores, max_miners=10)
                bt.logging.info(f"🏆 TOP VALID MINERS SELECTED FOR TASK {task_id}:")
                for rank, (miner_uid, score) in enumerate(top_miners, 1):
                    bt.logging.info(f"   #{rank:2d} | UID {miner_uid:3d} | Score: {score:.2f}")
                
                # Update miner performance tracking with only top miners
                # CRITICAL: Track hotkey+uid to handle UID reuse scenarios
                bt.logging.info(f"📈 UPDATING MINER PERFORMANCE (TOP {len(top_miners)} ONLY):")
                for miner_uid, score in top_miners:
                    # Get hotkey from metagraph for miner identity tracking (use cache if available)
                    try:
                        current_block = self.block if hasattr(self, 'block') else 0
                        hotkey = None
                        
                        # Try cache first
                        if hasattr(self, 'cache_manager'):
                            hotkey = self.cache_manager.get_cached_hotkey(miner_uid, current_block)
                        
                        # Fallback to metagraph if not cached
                        if not hotkey:
                            if miner_uid < len(self.metagraph.hotkeys):
                                hotkey = self.metagraph.hotkeys[miner_uid]
                                # Cache it
                                if hasattr(self, 'cache_manager'):
                                    self.cache_manager.set_hotkey_cache(miner_uid, hotkey, current_block)
                            else:
                                hotkey = None
                                bt.logging.warning(f"⚠️ Miner UID {miner_uid} out of metagraph range")
                        
                        miner_identity = f"{hotkey}_{miner_uid}" if hotkey else f"unknown_{miner_uid}"
                    except Exception as e:
                        hotkey = None
                        miner_identity = f"unknown_{miner_uid}"
                        bt.logging.warning(f"⚠️ Could not get hotkey for UID {miner_uid}: {e}")
                    if miner_uid not in miner_performance:
                        miner_performance[miner_uid] = {
                            'total_score': 0.0,
                            'task_count': 0,
                            'task_scores': {},
                            'top_rankings': {},  # Track top rankings per task
                            'hotkey': hotkey,  # Track hotkey for UID reuse handling
                            'miner_identity': miner_identity,  # Unique identifier
                            'uid': miner_uid
                        }
                    else:
                        # Verify hotkey hasn't changed (UID reuse detection)
                        if miner_performance[miner_uid].get('hotkey') != hotkey:
                            bt.logging.warning(f"⚠️ UID REUSE DETECTED for UID {miner_uid}!")
                            bt.logging.warning(f"   Old hotkey: {miner_performance[miner_uid].get('hotkey')}")
                            bt.logging.warning(f"   New hotkey: {hotkey}")
                            bt.logging.warning(f"   Creating new performance entry for new miner")
                            # Create new entry for new miner with same UID
                            miner_performance[miner_uid] = {
                                'total_score': 0.0,
                                'task_count': 0,
                                'task_scores': {},
                                'top_rankings': {},
                                'hotkey': hotkey,
                                'miner_identity': miner_identity,
                                'uid': miner_uid
                        }
                    
                    miner_performance[miner_uid]['total_score'] += score
                    miner_performance[miner_uid]['task_count'] += 1
                    miner_performance[miner_uid]['task_scores'][task_id] = score
                    
                    # Record ranking position for this task
                    ranking_position = next(i for i, (uid, _) in enumerate(top_miners, 1) if uid == miner_uid)
                    miner_performance[miner_uid]['top_rankings'][task_id] = ranking_position
                    
                    bt.logging.info(f"   Miner {miner_uid} ({miner_identity}):")
                    bt.logging.info(f"      Task Score: {score:.2f}")
                    bt.logging.info(f"      Ranking: #{ranking_position}")
                    bt.logging.info(f"      Running Total: {miner_performance[miner_uid]['total_score']:.2f}")
                    bt.logging.info(f"      Tasks Completed: {miner_performance[miner_uid]['task_count']}")
                
                bt.logging.info(f"✅ TASK {task_id} EVALUATION COMPLETED SUCCESSFULLY")
                
                # NOTE: Task will be marked as seen ONLY after weights are successfully set
                # This ensures miners are rewarded before task is marked as seen
                bt.logging.info(f"📝 Task {task_id} evaluation complete - will mark as seen after weights are set")
                
                bt.logging.info("=" * 80)
            
            # Generate performance rankings
            miner_rankings = await self.rank_miners_by_performance(miner_performance)
            
            # Generate comprehensive performance report
            performance_report = await self.generate_performance_report(miner_performance, miner_rankings)
            
            # Calculate final weights using new reward system
            final_weights = await self.calculate_new_reward_weights(miner_performance)
            
            # CRITICAL FIX: Check if we have any weights to set
            if not final_weights:
                bt.logging.warning("⚠️ No final weights calculated - skipping weight setting")
                bt.logging.info("🎯 Task evaluation completed (no weights to set)")
                bt.logging.info(f"📊 Processed {len(new_tasks)} tasks for {len(miner_performance)} miners")
                
                # Log completion without weight setting
                evaluation_time = time.time() - start_time
                bt.logging.info(f"⏱️  Total evaluation time: {evaluation_time:.2f} seconds")
                bt.logging.info(f"📊 Average time per task: {evaluation_time / len(new_tasks):.2f} seconds")
                
                # Log comprehensive evaluation summary
                current_epoch = getattr(self, 'current_epoch', 0)
                self.log_evaluation_summary(current_epoch, len(new_tasks), miner_performance)
                
                # Update performance metrics
                self.update_performance_metrics('evaluation_complete', success=True, 
                                             evaluation_time=evaluation_time, 
                                             tasks_processed=len(new_tasks),
                                             miners_evaluated=len(miner_performance))
                
                # Save evaluation history
                self.save_evaluation_history()
                return
            
            # Log final weight summary
            bt.logging.info("🎯 Final Weight Summary:")
            for miner_uid, weight in sorted(final_weights.items(), key=lambda x: x[1], reverse=True):
                performance = miner_performance.get(miner_uid, {})
                task_count = performance.get('task_count', 0)
                bt.logging.info(f"   Miner {miner_uid}: Weight={weight:.2f}, Tasks={task_count}")
            
            # Set weights on chain
            weights_set_successfully = await self.set_miner_weights(final_weights)
            
            # CRITICAL: Only mark tasks as seen if weights were successfully set
            # This ensures miners are rewarded before tasks are marked as seen
            if weights_set_successfully:
                bt.logging.info("✅ Weights set successfully - marking tasks as seen")
                for task_id in validator_performance.keys():
                    bt.logging.info(f"🏷️ Marking task {task_id} as evaluated (weights were set)...")
                    await self.mark_task_as_validator_evaluated(task_id, validator_performance[task_id])
                    # Add to in-memory cache to prevent re-evaluation
                    if hasattr(self, 'evaluated_tasks_cache'):
                        self.evaluated_tasks_cache.add(task_id)
                
                # Update last evaluation block to track that evaluation occurred
                if hasattr(self, 'block'):
                    self.last_evaluation_block = self.block
                    bt.logging.info(f"📊 Updated last_evaluation_block to {self.last_evaluation_block}")
            else:
                bt.logging.warning("⚠️ Weights were NOT set - tasks will NOT be marked as seen")
                bt.logging.warning("   Tasks will be re-evaluated in next iteration to ensure miners are rewarded")
            
            # Calculate and log evaluation performance
            evaluation_time = time.time() - start_time
            bt.logging.info(f"⏱️  Total evaluation time: {evaluation_time:.2f} seconds")
            bt.logging.info(f"📊 Average time per task: {evaluation_time / len(new_tasks):.2f} seconds")
            
            # Log completion
            bt.logging.info("🎯 Task evaluation and weight setting completed successfully!")
            bt.logging.info(f"📊 Processed {len(new_tasks)} tasks for {len(miner_performance)} miners")
            
            # Log comprehensive evaluation summary
            current_epoch = getattr(self, 'current_epoch', 0)
            self.log_evaluation_summary(current_epoch, len(new_tasks), miner_performance)
            
            # Update performance metrics
            self.update_performance_metrics('evaluation_complete', success=True, 
                                         evaluation_time=evaluation_time, 
                                         tasks_processed=len(new_tasks),
                                         miners_evaluated=len(miner_performance))
            
            # Save evaluation history
            self.save_evaluation_history()
            
        except Exception as e:
            bt.logging.error(f"❌ Error in task evaluation and weight setting: {str(e)}")
            self.update_performance_metrics('evaluation_complete', success=False, error=str(e))
            import traceback
            traceback.print_exc()

    async def fetch_completed_tasks_from_proxy(self) -> List[Dict]:
        """
        Fetch completed tasks from proxy server with miner responses attached.
        Only tasks with status 'completed' are considered for evaluation and rewarding.
        """
        try:
            bt.logging.info(f"🔍 Fetching completed tasks from proxy server: {self.proxy_server_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = self._get_auth_headers()
                response = await client.get(
                    f"{self.proxy_server_url}/api/v1/tasks/completed",
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    tasks = response.json()
                    bt.logging.info(f"📥 Successfully fetched {len(tasks)} tasks from proxy server")
                    
                    # Filter for ONLY tasks with status 'completed'
                    completed_tasks = []
                    other_status_tasks = []
                    
                    for task in tasks:
                        task_id = task.get('task_id', 'unknown')
                        task_status = task.get('status', 'unknown')
                        task_type = task.get('task_type', 'unknown')
                        miner_responses = task.get('miner_responses', [])
                        
                        if task_status == 'completed':
                            completed_tasks.append(task)
                            bt.logging.info(f"   ✅ Task {task_id}: {task_type} - Status: {task_status} - {len(miner_responses)} miner responses")
                        else:
                            other_status_tasks.append(task)
                            bt.logging.debug(f"   ⚠️ Task {task_id}: {task_type} - Status: {task_status} - Skipping (not completed)")
                    
                    bt.logging.info(f"📊 Task Status Breakdown:")
                    bt.logging.info(f"   ✅ Completed tasks: {len(completed_tasks)}")
                    bt.logging.info(f"   ⚠️ Other status tasks: {len(other_status_tasks)}")
                    
                    if other_status_tasks:
                        status_counts = {}
                        for task in other_status_tasks:
                            status = task.get('status', 'unknown')
                            status_counts[status] = status_counts.get(status, 0) + 1
                        
                        bt.logging.info(f"   📋 Other status breakdown:")
                        for status, count in status_counts.items():
                            bt.logging.info(f"      {status}: {count} tasks")
                    
                    if not completed_tasks:
                        bt.logging.info("📭 No completed tasks found for evaluation")
                        return []
                    
                    # Additional validation for completed tasks
                    valid_completed_tasks = []
                    invalid_tasks = []
                    
                    for task in completed_tasks:
                        task_id = task.get('task_id', 'unknown')
                        task_type = task.get('task_type', 'unknown')
                        miner_responses = task.get('miner_responses', [])
                        created_at = task.get('created_at')
                        completed_at = task.get('completed_at')
                        
                        # Validate required fields
                        validation_errors = []
                        
                        if not miner_responses:
                            validation_errors.append("No miner responses")
                        
                        if not task_type:
                            validation_errors.append("No task type")
                        
                        if not created_at:
                            validation_errors.append("No creation timestamp")
                        
                        # Check if task has been processed by miners
                        if miner_responses:
                            valid_responses = 0
                            for response in miner_responses:
                                miner_uid = response.get('miner_uid')
                                response_data = response.get('response', {})
                                
                                # Check for nested output data structure
                                # Response structure: response['response']['response_data']['output_data']
                                has_output = False
                                if isinstance(response_data, dict):
                                    # Check nested structure
                                    if 'output_data' in response_data:
                                        has_output = True
                                    elif 'response_data' in response_data:
                                        nested = response_data['response_data']
                                        if isinstance(nested, dict):
                                            # Check if nested has output_data dict
                                            if 'output_data' in nested:
                                                # output_data is a dict, check if it contains actual output
                                                output_data = nested['output_data']
                                                if isinstance(output_data, dict):
                                                    has_output = any(key in output_data for key in [
                                                        'transcript', 'audio_data', 'summary', 'translation', 
                                                        'result', 'output', 'audio_file', 'translated_text'
                                                    ])
                                                else:
                                                    has_output = bool(output_data)
                                            elif any(key in nested for key in [
                                                'transcript', 'audio_data', 'summary', 'translation', 
                                                'result', 'output', 'audio_file', 'translated_text'
                                            ]):
                                                # Nested data itself contains output fields
                                                has_output = True
                                    else:
                                        # Check for direct output fields
                                        has_output = any(key in response_data for key in [
                                            'output_data', 'transcript', 'audio_data', 'summary', 
                                            'translation', 'result', 'output', 'audio_file'
                                        ])
                                
                                # Check processing_time - can be at response level or nested
                                has_processing_time = (
                                    response.get('processing_time') is not None or
                                    (isinstance(response_data, dict) and response_data.get('processing_time') is not None)
                                )
                                
                                if (miner_uid is not None and 
                                    has_processing_time and
                                    response.get('submitted_at') is not None and
                                    has_output):
                                    valid_responses += 1
                            
                            if valid_responses == 0:
                                validation_errors.append("No valid miner responses")
                        
                        if validation_errors:
                            invalid_tasks.append({
                                'task_id': task_id,
                                'task_type': task_type,
                                'errors': validation_errors
                            })
                            bt.logging.warning(f"⚠️ Task {task_id} validation failed: {', '.join(validation_errors)}")
                        else:
                            valid_completed_tasks.append(task)
                            bt.logging.debug(f"   ✅ Task {task_id} validation passed")
                    
                    bt.logging.info(f"📊 Validation Results:")
                    bt.logging.info(f"   ✅ Valid completed tasks: {len(valid_completed_tasks)}")
                    bt.logging.info(f"   ❌ Invalid tasks: {len(invalid_tasks)}")
                    
                    if invalid_tasks:
                        bt.logging.info(f"   📋 Invalid task details:")
                        for invalid_task in invalid_tasks[:5]:  # Show first 5 invalid tasks
                            bt.logging.info(f"      Task {invalid_task['task_id']} ({invalid_task['task_type']}): {', '.join(invalid_task['errors'])}")
                        
                        if len(invalid_tasks) > 5:
                            bt.logging.info(f"      ... and {len(invalid_tasks) - 5} more invalid tasks")
                    
                    # Log final summary
                    bt.logging.info(f"🎯 Final Result: {len(valid_completed_tasks)} valid completed tasks ready for evaluation")
                    
                    # Log details about each valid completed task
                    for task in valid_completed_tasks:
                        task_id = task.get('task_id', 'unknown')
                        task_type = task.get('task_type', 'unknown')
                        miner_responses = task.get('miner_responses', [])
                        created_at = task.get('created_at', 'N/A')
                        completed_at = task.get('completed_at', 'N/A')
                        
                        bt.logging.info(f"   📋 Valid Task {task_id}:")
                        bt.logging.info(f"      Type: {task_type}")
                        bt.logging.info(f"      Created: {created_at}")
                        bt.logging.info(f"      Completed: {completed_at}")
                        bt.logging.info(f"      Miner Responses: {len(miner_responses)}")
                        
                        # Log miner response summary
                        for i, response in enumerate(miner_responses[:3], 1):  # Show first 3 responses
                            miner_uid = response.get('miner_uid', 'unknown')
                            processing_time = response.get('processing_time', 0)
                            accuracy_score = response.get('accuracy_score', 0)
                            submitted_at = response.get('submitted_at', 'N/A')
                            bt.logging.info(f"         Miner {i}: UID {miner_uid} | Time: {processing_time:.2f}s | Accuracy: {accuracy_score:.3f} | Submitted: {submitted_at}")
                        
                        if len(miner_responses) > 3:
                            bt.logging.info(f"         ... and {len(miner_responses) - 3} more miner responses")
                    
                    return valid_completed_tasks
                    
                else:
                    bt.logging.warning(f"⚠️ Proxy server returned status {response.status_code}")
                    bt.logging.debug(f"Response content: {response.text}")
                    return []
                    
        except Exception as e:
            bt.logging.error(f"❌ Error fetching completed tasks from proxy: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    # REMOVED: All pipeline execution methods - Validator does not execute pipelines
    # The validator only evaluates miner responses, it does not run tasks itself
    # Removed methods:
    # - execute_task_as_validator
    # - _extract_input_data_robust
    # - _validate_input_data_robust
    # - _download_and_extract_file_content
    # - _execute_pipeline_robust
    # - _check_pipeline_availability
    # - _log_task_execution_result
    # - execute_transcription_task
    # - execute_tts_task
    # - execute_summarization_task
    # - execute_video_transcription_task
    # - execute_text_translation_task
    # - execute_document_translation_task
    # - compare_transcription_results
    # - compare_tts_results
    # - compare_summarization_results
    # - compare_translation_results

    async def calculate_task_scores(self, task_id: str, task_type: str, validator_result: Optional[Dict], miner_responses: List[Dict]) -> Dict[int, float]:
        """
        Calculate scores for each miner based on response quality.
        Returns a dictionary mapping miner UIDs to their scores.
        Scores are calculated based on task type and capped at 500 as per requirement.
        Validator does not execute tasks - scores are based on miner response quality only.
        """
        try:
            bt.logging.info(f"📊 CALCULATING SCORES FOR TASK {task_id}")
            bt.logging.info(f"   Task Type: {task_type}")
            bt.logging.info(f"   Miner Responses: {len(miner_responses)}")
            
            miner_scores = {}
            score_breakdown = {}
            
            for i, miner_response in enumerate(miner_responses, 1):
                miner_uid = miner_response.get('miner_uid')
                if not miner_uid:
                    bt.logging.warning(f"⚠️ Miner response {i} missing miner_uid, skipping")
                    continue
                
                bt.logging.info(f"   🔍 Evaluating Miner {miner_uid} (Response {i}/{len(miner_responses)}):")
                
                # Calculate accuracy score based on response quality (no validator execution)
                accuracy_score = await self.calculate_accuracy_score_from_response(
                    miner_response, task_type
                )
                
                # Calculate speed score based on processing time
                # Extract from nested structure: response['response'] contains the miner's payload
                nested_response = miner_response.get('response', {})
                if isinstance(nested_response, str):
                    try:
                        import json
                        nested_response = json.loads(nested_response)
                    except:
                        nested_response = {}
                
                # Try to get processing_time from nested response first, then top level
                miner_processing_time = nested_response.get('processing_time') or miner_response.get('processing_time', 10.0)
                speed_score = self.calculate_speed_score(miner_processing_time, task_type)
                
                # Calculate quality score based on response structure and completeness
                quality_score = self.calculate_quality_score(miner_response, task_type)
                
                # Task type-specific scoring weights
                if task_type == 'transcription':
                    # Transcription: accuracy is most important
                    weights = {'accuracy': 0.65, 'speed': 0.25, 'quality': 0.10}
                elif task_type == 'video_transcription':
                    # Video transcription: accuracy is most important
                    weights = {'accuracy': 0.65, 'speed': 0.25, 'quality': 0.10}
                elif task_type == 'tts':
                    # TTS: quality and accuracy are important
                    weights = {'accuracy': 0.50, 'speed': 0.20, 'quality': 0.30}
                elif task_type == 'summarization':
                    # Summarization: accuracy and quality are important
                    weights = {'accuracy': 0.60, 'speed': 0.20, 'quality': 0.20}
                elif task_type in ['text_translation', 'document_translation']:
                    # Translation: accuracy is most important
                    weights = {'accuracy': 0.70, 'speed': 0.20, 'quality': 0.10}
                else:
                    # Default weights
                    weights = {'accuracy': 0.60, 'speed': 0.25, 'quality': 0.15}
                
                # Combined score with task type-specific weights
                combined_score = (
                    (accuracy_score * weights['accuracy']) + 
                    (speed_score * weights['speed']) + 
                    (quality_score * weights['quality'])
                )
                
                # Convert to 0-500 scale
                final_score = combined_score * 500.0
                
                # Ensure score doesn't exceed 500 (as per requirement)
                final_score = min(final_score, 500.0)
                
                miner_scores[miner_uid] = final_score
                
                # Store detailed score breakdown for logging
                score_breakdown[miner_uid] = {
                    'accuracy_score': accuracy_score,
                    'speed_score': speed_score,
                    'quality_score': quality_score,
                    'combined_score': combined_score,
                    'final_score': final_score,
                    'weights_used': weights,
                    'processing_time': miner_processing_time
                }
                
                bt.logging.info(f"      Accuracy Score: {accuracy_score:.4f} (Weight: {weights['accuracy']:.2f})")
                bt.logging.info(f"      Speed Score: {speed_score:.4f} (Weight: {weights['speed']:.2f})")
                bt.logging.info(f"      Quality Score: {quality_score:.4f} (Weight: {weights['quality']:.2f})")
                bt.logging.info(f"      Combined Score: {combined_score:.4f}")
                bt.logging.info(f"      Final Score: {final_score:.2f}/500")
                bt.logging.info(f"      Processing Time: {miner_processing_time:.3f}s")
            
            # Log score summary
            if miner_scores:
                scores_list = list(miner_scores.values())
                avg_score = sum(scores_list) / len(scores_list)
                max_score = max(scores_list)
                min_score = min(scores_list)
                
                bt.logging.info(f"   📊 Score Summary for Task {task_id}:")
                bt.logging.info(f"      Miners Evaluated: {len(miner_scores)}")
                bt.logging.info(f"      Average Score: {avg_score:.2f}")
                bt.logging.info(f"      Highest Score: {max_score:.2f}")
                bt.logging.info(f"      Lowest Score: {min_score:.2f}")
                bt.logging.info(f"      Score Range: {max_score - min_score:.2f}")
                
                # Show top 3 miners for this task
                top_miners = sorted(miner_scores.items(), key=lambda x: x[1], reverse=True)[:3]
                bt.logging.info(f"      🏆 Top Miners for Task {task_id}:")
                for rank, (uid, score) in enumerate(top_miners, 1):
                    breakdown = score_breakdown.get(uid, {})
                    bt.logging.info(f"         #{rank} | UID {uid:3d} | Score: {score:6.2f} | Accuracy: {breakdown.get('accuracy_score', 0):.3f} | Speed: {breakdown.get('speed_score', 0):.3f}")
            
            return miner_scores
            
        except Exception as e:
            bt.logging.error(f"❌ Error calculating task scores for task {task_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}

    async def calculate_accuracy_score_from_response(self, miner_response: Dict, task_type: str) -> float:
        """Calculate accuracy score based on miner response quality (no validator execution)"""
        try:
            # Extract output data from miner response
            output_data = None
            if isinstance(miner_response.get('response'), dict):
                response_data = miner_response['response'].get('response_data', {})
                if isinstance(response_data, dict):
                    output_data = response_data.get('output_data', {})
                    if not output_data:
                        output_data = response_data  # Use response_data directly if no output_data key
            elif isinstance(miner_response.get('response_data'), dict):
                output_data = miner_response['response_data'].get('output_data', {})
                if not output_data:
                    output_data = miner_response['response_data']
            elif isinstance(miner_response.get('output_data'), dict):
                output_data = miner_response['output_data']
            
            # Check if output data exists and has required fields
            if not output_data or not isinstance(output_data, dict):
                bt.logging.warning(f"   ⚠️ No valid output data found in miner response")
                return 0.0
            
            # Check for task-specific output fields
            has_valid_output = False
            if task_type in ['transcription', 'video_transcription']:
                has_valid_output = 'transcript' in output_data and len(str(output_data.get('transcript', ''))) > 0
            elif task_type == 'tts':
                has_valid_output = 'audio_data' in output_data or 'audio_file' in output_data
            elif task_type == 'summarization':
                has_valid_output = 'summary' in output_data and len(str(output_data.get('summary', ''))) > 10
            elif task_type in ['text_translation', 'document_translation']:
                has_valid_output = 'translated_text' in output_data or 'translation' in output_data
            else:
                # For unknown task types, check if output_data has any content
                has_valid_output = len(output_data) > 0
                
            if not has_valid_output:
                bt.logging.warning(f"   ⚠️ Output data missing required fields for {task_type}")
            return 0.0

            # Base score for having valid output
            base_score = 0.7
            
            # Add bonus for response quality indicators
            if miner_response.get('accuracy_score') is not None:
                # Use miner's own accuracy score if provided
                miner_acc = float(miner_response.get('accuracy_score', 0))
                base_score = max(base_score, miner_acc)
            
            # Check response completeness
            output_size = len(str(output_data))
            if output_size > 100:  # Substantial output
                base_score = min(1.0, base_score + 0.1)
            
            bt.logging.debug(f"   Accuracy score: {base_score:.4f} (based on response quality)")
            return base_score
                
        except Exception as e:
            bt.logging.error(f"❌ Error calculating accuracy score from response: {str(e)}")
            import traceback
            traceback.print_exc()
            return 0.0

    # REMOVED: All comparison methods - Validator does not execute tasks, so no comparison needed
    # - compare_transcription_results
    # - compare_tts_results
    # - compare_summarization_results
    # - compare_translation_results

    async def calculate_new_reward_weights(self, miner_performance: Dict) -> Dict[int, float]:
        """
        Calculate final weights using new reward mechanism:
        - 55% Uptime (miner availability)
        - 25% Invocation count (successful user inference requests)
        - 15% Diversity (models/tasks served)
        - 5% Bounty count (cold-start or priority task completions)
        
        Also considers response speed for ranking (only for participating miners)
        """
        try:
            bt.logging.info("📊 CALCULATING NEW REWARD WEIGHTS")
            bt.logging.info("=" * 60)
            bt.logging.info("Reward Distribution:")
            bt.logging.info("   55% - Uptime")
            bt.logging.info("   25% - Invocation Count")
            bt.logging.info("   15% - Diversity")
            bt.logging.info("    5% - Bounty Count")
            bt.logging.info("=" * 60)
            
            final_weights = {}
            weight_summary = {}
            
            # Get miner metrics from database or calculate from performance data
            for miner_uid, performance in miner_performance.items():
                bt.logging.info(f"\n🔍 Calculating weights for Miner {miner_uid}:")
                
                # Get or calculate metrics
                metrics = await self.get_miner_metrics(miner_uid, performance)
                
                # Calculate component scores (normalized to 0-1)
                uptime_score = metrics.get('uptime_score', 0.0)  # Already normalized
                invocation_score = metrics.get('invocation_score', 0.0)  # Normalized
                diversity_score = metrics.get('diversity_score', 0.0)  # Normalized
                bounty_score = metrics.get('bounty_score', 0.0)  # Normalized
                
                # Calculate weighted final score (0-1 scale)
                final_score = (
                    (uptime_score * 0.55) +
                    (invocation_score * 0.25) +
                    (diversity_score * 0.15) +
                    (bounty_score * 0.05)
                )
                
                # Convert to 0-500 scale (as per requirement)
                final_weight = final_score * 500.0
                final_weight = min(final_weight, 500.0)  # Cap at 500
                
                final_weights[miner_uid] = final_weight
                
                # Store summary
                weight_summary[miner_uid] = {
                    'uptime_score': uptime_score,
                    'uptime_percentage': metrics.get('uptime_percentage', 0.0),
                    'invocation_count': metrics.get('invocation_count', 0),
                    'invocation_score': invocation_score,
                    'diversity_count': metrics.get('diversity_count', 0),
                    'diversity_score': diversity_score,
                    'bounty_count': metrics.get('bounty_count', 0),
                    'bounty_score': bounty_score,
                    'final_score': final_score,
                    'final_weight': final_weight,
                    'average_response_time': metrics.get('average_response_time', 0.0)
                }
                
                bt.logging.info(f"   Uptime: {uptime_score:.4f} ({metrics.get('uptime_percentage', 0):.1f}%)")
                bt.logging.info(f"   Invocation: {invocation_score:.4f} ({metrics.get('invocation_count', 0)} requests)")
                bt.logging.info(f"   Diversity: {diversity_score:.4f} ({metrics.get('diversity_count', 0)} unique)")
                bt.logging.info(f"   Bounty: {bounty_score:.4f} ({metrics.get('bounty_count', 0)} tasks)")
                bt.logging.info(f"   Final Weight: {final_weight:.2f}/500")
                bt.logging.info(f"   Avg Response Time: {metrics.get('average_response_time', 0):.3f}s")
            
            # Log summary
            if final_weights:
                sorted_miners = sorted(final_weights.items(), key=lambda x: x[1], reverse=True)
                bt.logging.info(f"\n🏆 Top Miners by New Reward System:")
                for rank, (uid, weight) in enumerate(sorted_miners[:10], 1):
                    summary = weight_summary.get(uid, {})
                    bt.logging.info(
                        f"   #{rank:2d} | UID {uid:3d} | Weight: {weight:6.2f} | "
                        f"Uptime: {summary.get('uptime_score', 0):.3f} | "
                        f"Invoke: {summary.get('invocation_count', 0):3d} | "
                        f"Div: {summary.get('diversity_count', 0):2d} | "
                        f"Bounty: {summary.get('bounty_count', 0):2d}"
                    )
            
            return final_weights
            
        except Exception as e:
            bt.logging.error(f"❌ Error calculating new reward weights: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}
    
    async def get_miner_metrics(self, miner_uid: int, performance: Dict) -> Dict:
        """Get or calculate miner metrics for reward calculation"""
        try:
            # Try to get from database first
            metrics = await self.fetch_miner_metrics_from_db(miner_uid)
            if metrics:
                return metrics
            
            # Calculate from performance data if not in DB
            return self.calculate_metrics_from_performance(miner_uid, performance)
            
        except Exception as e:
            bt.logging.warning(f"⚠️ Error getting metrics for miner {miner_uid}: {e}")
            return self.get_default_metrics()
    
    async def fetch_miner_metrics_from_db(self, miner_uid: int) -> Optional[Dict]:
        """
        Fetch miner metrics from database using hotkey+uid combination.
        This handles UID reuse scenarios by tracking miner identity, not just UID.
        """
        try:
            # Get hotkey from metagraph to create miner identity
            if miner_uid >= len(self.metagraph.hotkeys):
                bt.logging.warning(f"⚠️ Miner UID {miner_uid} out of range")
                return None
            
            hotkey = self.metagraph.hotkeys[miner_uid]
            coldkey = self.metagraph.coldkeys[miner_uid] if hasattr(self.metagraph, 'coldkeys') and miner_uid < len(self.metagraph.coldkeys) else None
            miner_identity = f"{hotkey}_{miner_uid}"
            
            bt.logging.debug(f"🔍 Fetching metrics for miner_identity: {miner_identity} (UID: {miner_uid})")
            
            # Query proxy server API for miner metrics
            if hasattr(self, 'proxy_server_url') and self.proxy_server_url:
                try:
                    headers = self._get_auth_headers()
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        # Try to get metrics by miner_identity
                        response = await client.get(
                            f"{self.proxy_server_url}/api/v1/miners/{miner_uid}/metrics",
                            headers=headers,
                            params={"hotkey": hotkey, "miner_identity": miner_identity}
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('success') and data.get('metrics'):
                                metrics = data['metrics']
                                # Verify UID and hotkey still match (handle UID reuse)
                                if metrics.get('uid') == miner_uid and metrics.get('hotkey') == hotkey:
                                    bt.logging.debug(f"✅ Found metrics for {miner_identity}")
                                    return metrics
                                else:
                                    bt.logging.warning(f"⚠️ UID reuse detected! Hotkey changed for UID {miner_uid}")
                                    # UID was reused - return None to create new metrics
                                    return None
                except Exception as e:
                    bt.logging.debug(f"⚠️ Could not fetch metrics from proxy: {e}")
            
            # Fallback: return None to use performance-based calculation
            return None
        except Exception as e:
            bt.logging.warning(f"⚠️ Error fetching metrics from DB: {e}")
            return None
    
    def calculate_metrics_from_performance(self, miner_uid: int, performance: Dict) -> Dict:
        """Calculate metrics from performance data"""
        try:
            task_count = performance.get('task_count', 0)
            task_scores = performance.get('task_scores', {})
            
            # Calculate uptime (simplified - based on task participation)
            # In real implementation, this would track actual uptime periods
            uptime_percentage = min(1.0, task_count / 100.0) if task_count > 0 else 0.0
            uptime_score = uptime_percentage
            
            # Invocation count (successful user requests)
            successful_tasks = sum(1 for score in task_scores.values() if score > 0)
            invocation_count = successful_tasks
            max_invocations = max(1, max([invocation_count for p in [performance] for _ in [1]], default=1))
            invocation_score = min(1.0, invocation_count / max_invocations) if max_invocations > 0 else 0.0
            
            # Diversity (unique task types/models)
            # Extract from task_scores keys or performance data
            unique_tasks = set(task_scores.keys())
            diversity_count = len(unique_tasks)
            max_diversity = max(1, 10)  # Assume max 10 different task types
            diversity_score = min(1.0, diversity_count / max_diversity)
            
            # Bounty count (priority/cold-start tasks)
            # This would need to be tracked separately
            bounty_count = 0
            bounty_score = 0.0
            
            # Response speed
            total_time = sum(performance.get('task_times', {}).values())
            response_count = len(performance.get('task_times', {}))
            average_response_time = total_time / response_count if response_count > 0 else 0.0
            
            return {
                'uptime_score': uptime_score,
                'uptime_percentage': uptime_percentage * 100,
                'invocation_count': invocation_count,
                'invocation_score': invocation_score,
                'diversity_count': diversity_count,
                'diversity_score': diversity_score,
                'bounty_count': bounty_count,
                'bounty_score': bounty_score,
                'average_response_time': average_response_time
            }
            
        except Exception as e:
            bt.logging.warning(f"⚠️ Error calculating metrics: {e}")
            return self.get_default_metrics()
    
    def get_default_metrics(self) -> Dict:
        """Return default metrics for miners with no data"""
        return {
            'uptime_score': 0.0,
            'uptime_percentage': 0.0,
            'invocation_count': 0,
            'invocation_score': 0.0,
            'diversity_count': 0,
            'diversity_score': 0.0,
            'bounty_count': 0,
            'bounty_score': 0.0,
            'average_response_time': 0.0
        }

    async def calculate_final_weights(self, miner_performance: Dict) -> Dict[int, float]:
        """
        Calculate final weights for all miners based on cumulative performance across all tasks.
        Each miner's total score is the sum of all their scores from all tasks they participated in.
        Weights are capped at 500 as per requirement.
        """
        try:
            bt.logging.info("⚖️ CALCULATING FINAL WEIGHTS FOR ALL MINERS")
            bt.logging.info("=" * 60)
            
            # CRITICAL FIX: Check if we have any miner performance data
            if not miner_performance:
                bt.logging.warning("⚠️ No miner performance data available - cannot calculate weights")
                return {}
            
            final_weights = {}
            weight_summary = {}
            
            # Calculate weights for each miner
            for miner_uid, performance in miner_performance.items():
                total_score = performance['total_score']
                task_count = performance['task_count']
                task_scores = performance.get('task_scores', {})
                
                bt.logging.info(f"🔍 Miner {miner_uid}:")
                bt.logging.info(f"   Tasks Participated: {task_count}")
                bt.logging.info(f"   Raw Total Score: {total_score:.2f}")
                
                # Show individual task scores
                if task_scores:
                    bt.logging.info(f"   Individual Task Scores:")
                    for task_id, score in sorted(task_scores.items(), key=lambda x: x[1], reverse=True):
                        bt.logging.info(f"      Task {task_id[:8]}...: {score:.2f}")
                
                # Calculate average score per task
                avg_score = total_score / task_count if task_count > 0 else 0.0
                bt.logging.info(f"   Average Score per Task: {avg_score:.2f}")
                
                # Ensure total score doesn't exceed 500 (as per requirement)
                # This is the cumulative score across all tasks
                capped_total_score = min(total_score, 500.0)
                
                # Calculate final weight based on capped total score
                # Higher total score = higher weight
                final_weight = capped_total_score
                
                final_weights[miner_uid] = final_weight
                
                # Store summary information
                weight_summary[miner_uid] = {
                    'total_score': total_score,
                    'task_count': task_count,
                    'avg_score_per_task': avg_score,
                    'capped_total_score': capped_total_score,
                    'final_weight': final_weight,
                    'was_capped': total_score > 500.0
                }
                
                bt.logging.info(f"   Capped Total Score: {capped_total_score:.2f}")
                bt.logging.info(f"   Final Weight: {final_weight:.2f}")
                if total_score > 500.0:
                    bt.logging.info(f"   ⚠️  Score was capped from {total_score:.2f} to 500.0")
                bt.logging.info("")
            
            # CRITICAL FIX: Check if we calculated any weights
            if not final_weights:
                bt.logging.warning("⚠️ No final weights calculated - returning empty dict")
                return {}
            
            # Log comprehensive weight summary
            bt.logging.info("📊 COMPREHENSIVE WEIGHT SUMMARY")
            bt.logging.info("=" * 60)
            
            # Sort miners by final weight (descending)
            sorted_miners = sorted(final_weights.items(), key=lambda x: x[1], reverse=True)
            
            max_weight = max(final_weights.values())
            min_weight = min(final_weights.values())
            avg_weight = sum(final_weights.values()) / len(final_weights)
            total_weight_sum = sum(final_weights.values())
            
            bt.logging.info(f"🏆 Top Performers:")
            for rank, (uid, weight) in enumerate(sorted_miners[:5], 1):
                summary = weight_summary.get(uid, {})
                bt.logging.info(f"   #{rank:2d} | UID {uid:3d} | Weight: {weight:6.2f} | Tasks: {summary.get('task_count', 0):2d} | Avg: {summary.get('avg_score_per_task', 0):6.2f}")
            
            if len(sorted_miners) > 5:
                bt.logging.info(f"   ... and {len(sorted_miners) - 5} more miners")
            
            bt.logging.info(f"\n📈 Weight Statistics:")
            bt.logging.info(f"   Total Miners: {len(final_weights)}")
            bt.logging.info(f"   Total Weight Sum: {total_weight_sum:.2f}")
            bt.logging.info(f"   Maximum Weight: {max_weight:.2f}")
            bt.logging.info(f"   Minimum Weight: {min_weight:.2f}")
            bt.logging.info(f"   Average Weight: {avg_weight:.2f}")
            bt.logging.info(f"   Weight Range: {max_weight - min_weight:.2f}")
            
            # Check if any miners hit the 500 cap
            capped_miners = [uid for uid, weight in final_weights.items() if weight >= 500.0]
            if capped_miners:
                bt.logging.info(f"\n🏆 Miners at Maximum Score (500): {len(capped_miners)}")
                for uid in capped_miners:
                    summary = weight_summary.get(uid, {})
                    bt.logging.info(f"   UID {uid:3d}: Raw Score {summary.get('total_score', 0):.2f} → Capped to 500.0")
            
            return final_weights
            
        except Exception as e:
            bt.logging.error(f"❌ Error calculating final weights: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}

    async def set_miner_weights(self, final_weights: Dict[int, float]) -> bool:
        """
        Set miner weights on the blockchain
        
        Returns:
            True if weights were successfully set, False otherwise
        """
        try:
            bt.logging.info("🔗 Setting miner weights on blockchain...")
            
            # Check if we have any weights to set
            if not final_weights:
                bt.logging.warning("⚠️ No miner weights to set - skipping weight setting")
                return False
            
            # Convert to lists for bittensor
            uids = list(final_weights.keys())
            weights = list(final_weights.values())
            
            # CRITICAL FIX: Handle division by zero and empty weights
            total_weight = sum(weights)
            if total_weight <= 0:
                bt.logging.warning(f"⚠️ Total weight is {total_weight} - cannot normalize weights")
                bt.logging.info("   Setting equal weights for all miners to prevent division by zero")
                normalized_weights = [1.0 / len(weights)] * len(weights)
            else:
                # Normalize weights to sum to 1.0
                normalized_weights = [w / total_weight for w in weights]
            
            bt.logging.info(f"📊 Weight normalization:")
            bt.logging.info(f"   Total weight: {total_weight}")
            bt.logging.info(f"   Miners with tasks: {len(uids)}")
            bt.logging.info(f"   Normalized weights: {[f'{w:.4f}' for w in normalized_weights]}")
            
            # FIXED: Only set weights for miners that actually completed tasks
            # Don't initialize scores for all miners in metagraph - only for working miners
            bt.logging.info(f"🎯 SMART WEIGHT SETTING - Only active miners get weights:")
            bt.logging.info(f"   Active miners (did tasks): {len(uids)}")
            bt.logging.info(f"   Total miners in network: {self.metagraph.n}")
            bt.logging.info(f"   Efficiency gain: Setting weights for {len(uids)} miners instead of {self.metagraph.n}")
            
            # Create weight tensor only for miners that did work
            weights_tensor = torch.zeros(self.metagraph.n, dtype=torch.float32)
            
            for i, uid in enumerate(uids):
                if uid < len(weights_tensor):
                    weights_tensor[uid] = normalized_weights[i]
                    bt.logging.info(f"   Miner {uid}: weight = {normalized_weights[i]:.4f}")
                else:
                    bt.logging.warning(f"   ⚠️ Miner UID {uid} is out of range for metagraph size {len(weights_tensor)}")
            
            # Only set weights for miners that have done work
            # All other miners will have 0 weight (default)
            bt.logging.info(f"📊 Weight Distribution Summary:")
            active_miners = sum(1 for w in weights_tensor if w > 0)
            bt.logging.info(f"   Active miners (weight > 0): {active_miners}")
            bt.logging.info(f"   Inactive miners (weight = 0): {self.metagraph.n - active_miners}")
            bt.logging.info(f"   Total miners in metagraph: {self.metagraph.n}")
            
            # Set the scores and call our custom set_weights method
            self.scores = weights_tensor.numpy()
            weights_set = self.set_weights()
            
            if weights_set:
                bt.logging.info(f"✅ Successfully set weights for {len(uids)} miners")
                return True
            else:
                bt.logging.error(f"❌ Failed to set weights for {len(uids)} miners")
                return False
            
        except Exception as e:
            bt.logging.error(f"❌ Error setting miner weights: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    async def rank_miners_by_performance(self, miner_performance: Dict) -> List[Dict]:
        """Rank miners by their performance across all tasks, considering response speed"""
        try:
            bt.logging.info("🏆 Ranking miners by performance (with response speed consideration)...")
            
            # Convert to list for sorting
            miner_rankings = []
            
            for miner_uid, performance in miner_performance.items():
                total_score = performance['total_score']
                task_count = performance['task_count']
                avg_score = total_score / task_count if task_count > 0 else 0.0
                
                # Calculate capped score (max 500)
                capped_score = min(total_score, 500.0)
                
                # Calculate average response time from task times (only for participating miners)
                task_times = performance.get('task_times', {})
                if task_times:
                    avg_response_time = sum(task_times.values()) / len(task_times)
                else:
                    avg_response_time = 0.0
                
                # Speed bonus: faster miners get a small boost (max 5% bonus)
                # Inverse relationship: faster = higher bonus
                if avg_response_time > 0:
                    # Normalize: 0-10s range, faster is better
                    speed_bonus = max(0, (10.0 - avg_response_time) / 10.0) * 0.05
                    capped_score_with_speed = capped_score * (1.0 + speed_bonus)
                    capped_score_with_speed = min(capped_score_with_speed, 500.0)  # Still cap at 500
                else:
                    speed_bonus = 0.0
                    capped_score_with_speed = capped_score
                
                miner_rankings.append({
                    'miner_uid': miner_uid,
                    'total_score': total_score,
                    'capped_score': capped_score,
                    'capped_score_with_speed': capped_score_with_speed,
                    'task_count': task_count,
                    'avg_score_per_task': avg_score,
                    'avg_response_time': avg_response_time,
                    'speed_bonus': speed_bonus,
                    'task_scores': performance['task_scores']
                })
            
            # Sort by capped score with speed consideration (descending)
            miner_rankings.sort(key=lambda x: x['capped_score_with_speed'], reverse=True)
            
            # Add rank information
            for i, ranking in enumerate(miner_rankings):
                ranking['rank'] = i + 1
                ranking['percentile'] = ((len(miner_rankings) - i) / len(miner_rankings)) * 100
            
            # Log rankings
            bt.logging.info("📊 Miner Rankings:")
            for ranking in miner_rankings[:10]:  # Top 10
                bt.logging.info(f"   #{ranking['rank']:2d} | UID {ranking['miner_uid']:3d} | Score: {ranking['capped_score']:6.2f} | Tasks: {ranking['task_count']:2d} | Avg: {ranking['avg_score_per_task']:6.2f} | Percentile: {ranking['percentile']:5.1f}%")
            
            if len(miner_rankings) > 10:
                bt.logging.info(f"   ... and {len(miner_rankings) - 10} more miners")
            
            return miner_rankings
            
        except Exception as e:
            bt.logging.error(f"❌ Error ranking miners: {str(e)}")
            return []

    async def generate_performance_report(self, miner_performance: Dict, miner_rankings: List[Dict]) -> Dict:
        """Generate a comprehensive performance report"""
        try:
            bt.logging.info("📋 Generating performance report...")
            
            if not miner_performance:
                return {"error": "No miner performance data available"}
            
            # Calculate statistics
            total_miners = len(miner_performance)
            total_tasks = sum(perf['task_count'] for perf in miner_performance.values())
            total_score = sum(perf['total_score'] for perf in miner_performance.values())
            
            # Score distribution
            score_ranges = {
                'excellent': 0,  # 400-500
                'good': 0,        # 300-399
                'average': 0,     # 200-299
                'below_average': 0, # 100-199
                'poor': 0         # 0-99
            }
            
            for ranking in miner_rankings:
                capped_score = ranking['capped_score']
                if capped_score >= 400:
                    score_ranges['excellent'] += 1
                elif capped_score >= 300:
                    score_ranges['good'] += 1
                elif capped_score >= 200:
                    score_ranges['average'] += 1
                elif capped_score >= 100:
                    score_ranges['below_average'] += 1
                else:
                    score_ranges['poor'] += 1
            
            # Top performers
            top_performers = miner_rankings[:5] if len(miner_rankings) >= 5 else miner_rankings
            
            # Miners at max score
            max_score_miners = [r for r in miner_rankings if r['capped_score'] >= 500.0]
            
            report = {
                'summary': {
                    'total_miners': total_miners,
                    'total_tasks_evaluated': total_tasks,
                    'total_score_distributed': total_score,
                    'average_score_per_miner': total_score / total_miners if total_miners > 0 else 0,
                    'average_tasks_per_miner': total_tasks / total_miners if total_miners > 0 else 0
                },
                'score_distribution': score_ranges,
                'top_performers': [
                    {
                        'rank': r['rank'],
                        'miner_uid': r['miner_uid'],
                        'capped_score': r['capped_score'],
                        'task_count': r['task_count'],
                        'avg_score_per_task': r['avg_score_per_task']
                    } for r in top_performers
                ],
                'max_score_miners': [
                    {
                        'miner_uid': r['miner_uid'],
                        'total_score': r['total_score'],
                        'task_count': r['task_count']
                    } for r in max_score_miners
                ],
                'performance_metrics': {
                    'highest_score': max(r['capped_score'] for r in miner_rankings) if miner_rankings else 0,
                    'lowest_score': min(r['capped_score'] for r in miner_rankings) if miner_rankings else 0,
                    'score_standard_deviation': self._calculate_std_dev([r['capped_score'] for r in miner_rankings]),
                    'median_score': self._calculate_median([r['capped_score'] for r in miner_rankings])
                }
            }
            
            # Log report summary
            bt.logging.info("📊 Performance Report Summary:")
            bt.logging.info(f"   Total Miners: {total_miners}")
            bt.logging.info(f"   Total Tasks: {total_tasks}")
            bt.logging.info(f"   Score Distribution: Excellent={score_ranges['excellent']}, Good={score_ranges['good']}, Average={score_ranges['average']}, Below={score_ranges['below_average']}, Poor={score_ranges['poor']}")
            bt.logging.info(f"   Top Score: {report['performance_metrics']['highest_score']:.2f}")
            bt.logging.info(f"   Miners at Max Score (500): {len(max_score_miners)}")
            
            return report
            
        except Exception as e:
            bt.logging.error(f"❌ Error generating performance report: {str(e)}")
            return {"error": str(e)}

    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation of a list of values"""
        try:
            if not values:
                return 0.0
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            return variance ** 0.5
        except:
            return 0.0

    def _calculate_median(self, values: List[float]) -> float:
        """Calculate median of a list of values"""
        try:
            if not values:
                return 0.0
            sorted_values = sorted(values)
            n = len(sorted_values)
            if n % 2 == 0:
                return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
            else:
                return sorted_values[n//2]
        except:
            return 0.0

    async def save_performance_report(self, performance_report: Dict):
        """Save performance report for future reference"""
        try:
            import json
            from datetime import datetime
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
            
            # Save to logs directory
            import os
            logs_dir = "logs/validator"
            os.makedirs(logs_dir, exist_ok=True)
            
            filepath = os.path.join(logs_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(performance_report, f, indent=2, default=str)
            
            bt.logging.info(f"💾 Performance report saved to: {filepath}")
            
        except Exception as e:
            bt.logging.warning(f"⚠️ Failed to save performance report: {str(e)}")

    async def test_proxy_server_connection(self):
        """Test connection to proxy server and show data structure"""
        max_retries = 3
        base_timeout = 60
        
        try:
            bt.logging.info(f"🔍 Testing proxy server connection: {self.proxy_server_url}")
            
            async with httpx.AsyncClient(timeout=base_timeout) as client:
                # Test basic connectivity (non-critical, don't retry)
                try:
                    response = await client.get(f"{self.proxy_server_url}/health", timeout=5.0)
                    if response.status_code == 200:
                        bt.logging.info("✅ Proxy server health check successful")
                    else:
                        bt.logging.warning(f"⚠️ Proxy server health check returned status {response.status_code}")
                except:
                    bt.logging.warning("⚠️ Proxy server health endpoint not available, continuing with main test")
                
                # Test completed tasks endpoint with retry logic
                bt.logging.info("🔍 Testing completed tasks endpoint...")
                headers = self._get_auth_headers()
                
                for attempt in range(max_retries):
                    try:
                        timeout = base_timeout * (attempt + 1)
                        bt.logging.debug(f"   Attempt {attempt + 1}/{max_retries} with {timeout}s timeout...")
                        
                        response = await client.get(
                            f"{self.proxy_server_url}/api/v1/tasks/completed",
                            headers=headers,
                            timeout=timeout
                        )
                        
                        if response.status_code == 200:
                            tasks = response.json()
                            bt.logging.info(f"✅ Successfully connected to proxy server")
                            bt.logging.info(f"📊 Found {len(tasks)} completed tasks")
                            
                            if tasks:
                                # Show sample task structure
                                sample_task = tasks[0]
                                bt.logging.info("📋 Sample task structure:")
                                bt.logging.info(f"   Task ID: {sample_task.get('task_id', 'N/A')}")
                                bt.logging.info(f"   Task Type: {sample_task.get('task_type', 'N/A')}")
                                bt.logging.info(f"   Status: {sample_task.get('status', 'N/A')}")
                                bt.logging.info(f"   Miner Responses: {len(sample_task.get('miner_responses', []))}")
                                
                                # Show sample miner response structure
                                miner_responses = sample_task.get('miner_responses', [])
                                if miner_responses:
                                    sample_response = miner_responses[0]
                                    bt.logging.info("📊 Sample miner response structure:")
                                    bt.logging.info(f"   Miner UID: {sample_response.get('miner_uid', 'N/A')}")
                                    bt.logging.info(f"   Processing Time: {sample_response.get('processing_time', 'N/A')}")
                                    bt.logging.info(f"   Accuracy Score: {sample_response.get('accuracy_score', 'N/A')}")
                                    bt.logging.info(f"   Response Data Keys: {list(sample_response.get('response_data', {}).keys())}")
                            else:
                                bt.logging.info("📭 No completed tasks found in proxy server")
                                
                            return True
                            
                        else:
                            bt.logging.warning(f"⚠️ Proxy server returned status {response.status_code}")
                            if attempt < max_retries - 1:
                                wait_time = 2 ** attempt
                                bt.logging.info(f"   Retrying in {wait_time}s...")
                                await asyncio.sleep(wait_time)
                            else:
                                bt.logging.error(f"❌ Proxy server returned status {response.status_code} after {max_retries} attempts")
                                bt.logging.debug(f"Response content: {response.text}")
                                return False
                                
                    except httpx.ReadTimeout as e:
                        timeout_seconds = base_timeout * (attempt + 1)
                        bt.logging.warning(f"⏰ Proxy server request timed out after {timeout_seconds}s (attempt {attempt + 1}/{max_retries})")
                        bt.logging.info(f"   The proxy server is taking longer than expected to respond. This may be due to high load or network issues.")
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            next_timeout = base_timeout * (attempt + 2)
                            bt.logging.info(f"   ⏳ Retrying in {wait_time}s with increased timeout ({next_timeout}s)...")
                            await asyncio.sleep(wait_time)
                        else:
                            bt.logging.error(f"❌ Connection failed: Proxy server did not respond within {timeout_seconds}s after {max_retries} attempts")
                            bt.logging.info(f"   💡 Possible causes: Proxy server is down, network issues, or server overload")
                            return False
                            
                    except httpx.RequestException as e:
                        error_msg = str(e)
                        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                            timeout_seconds = base_timeout * (attempt + 1)
                            bt.logging.warning(f"⏰ Request timeout after {timeout_seconds}s (attempt {attempt + 1}/{max_retries})")
                        else:
                            bt.logging.warning(f"⚠️  Network error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt
                            bt.logging.info(f"   ⏳ Retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            bt.logging.error(f"❌ Failed to connect to proxy server after {max_retries} attempts")
                            bt.logging.info(f"   💡 Check your network connection and verify the proxy server URL is correct")
                            return False
                            
                return False
                    
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                bt.logging.error(f"⏰ Connection timeout: Proxy server did not respond in time")
                bt.logging.info(f"   💡 Possible causes: Server overload, network issues, or incorrect proxy URL")
            else:
                bt.logging.error(f"❌ Unexpected error testing proxy server connection: {error_msg}")
                bt.logging.debug(f"   Full error details: {error_msg}")
            return False

    def _get_pipeline_name(self, task_type: str) -> str:
        """Get the pipeline name for a given task type"""
        pipeline_map = {
            'transcription': 'TranscriptionPipeline (Whisper)',
            'tts': 'TTSPipeline (Coqui TTS)',
            'summarization': 'SummarizationPipeline (BART)'
        }
        return pipeline_map.get(task_type, f'Unknown Pipeline ({task_type})')
    
    def _get_pipeline_description(self, task_type: str) -> str:
        """Get a detailed description of the pipeline for a given task type"""
        descriptions = {
            'transcription': {
                'name': 'TranscriptionPipeline',
                'model': 'Whisper (OpenAI)',
                'capability': 'Audio to Text conversion',
                'languages': 'Multi-language support',
                'input': 'Audio data (base64 encoded)',
                'output': 'Transcribed text with confidence'
            },
            'tts': {
                'name': 'TTSPipeline',
                'model': 'Coqui TTS (Tacotron2-DDC)',
                'capability': 'Text to Speech synthesis',
                'languages': 'Multi-language support',
                'input': 'Text data',
                'output': 'Audio data with duration'
            },
            'summarization': {
                'name': 'SummarizationPipeline',
                'model': 'BART Large CNN (Facebook)',
                'capability': 'Text summarization',
                'languages': 'Multi-language support',
                'input': 'Long text data',
                'output': 'Summarized text with key points'
            }
        }
        
        desc = descriptions.get(task_type, {})
        if desc:
            return f"{desc['name']} using {desc['model']} for {desc['capability']}"
        else:
            return f"Unknown pipeline for task type: {task_type}"

    async def select_top_miners_for_task(self, task_scores: Dict[int, float], max_miners: int = 10) -> List[tuple]:
        """
        Select top miners for a task based on performance scores.
        Returns list of tuples (miner_uid, score) sorted by score (descending).
        """
        try:
            bt.logging.info(f"🏆 Selecting top {max_miners} miners from {len(task_scores)} total miners")
            
            # Sort miners by score (descending)
            sorted_miners = sorted(task_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Take top max_miners
            top_miners = sorted_miners[:max_miners]
            
            bt.logging.info(f"✅ Selected top {len(top_miners)} miners:")
            for rank, (miner_uid, score) in enumerate(top_miners, 1):
                bt.logging.info(f"   #{rank:2d} | UID {miner_uid:3d} | Score: {score:.2f}")
            
            return top_miners
            
        except Exception as e:
            bt.logging.error(f"❌ Error selecting top miners: {str(e)}")
            return []

    async def mark_task_as_validator_evaluated(self, task_id: str, validator_performance: Dict):
        """Mark a task as evaluated by this validator to prevent re-evaluation"""
        try:
            validator_uid = getattr(self, 'uid', None)
            validator_identifier = f"validator_{validator_uid}" if validator_uid else f"validator_{self.wallet.hotkey.ss58_address}"
            
            bt.logging.info(f"🏷️ Marking task {task_id} as evaluated by validator {validator_identifier}...")
            
            # Add to in-memory cache
            self.evaluated_tasks_cache.add(task_id)
            
            # Mark task in database via proxy server API
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{self.proxy_server_url}/api/v1/validators/mark-task-seen",
                        json={
                            'task_id': task_id,
                            'validator_uid': validator_uid,
                            'validator_identifier': validator_identifier,
                            'evaluated_at': datetime.now().isoformat()
                        }
                    )
                    if response.status_code == 200:
                        bt.logging.info(f"✅ Task {task_id} marked as seen in database")
                    else:
                        bt.logging.warning(f"⚠️ Failed to mark task in database: {response.status_code}")
            except Exception as e:
                bt.logging.warning(f"⚠️ Error marking task in database: {e}")
            
            # Update evaluation history
            current_epoch = getattr(self, 'current_epoch', 0)
            if current_epoch not in self.evaluation_history:
                self.evaluation_history[current_epoch] = {
                    'tasks_evaluated': [],
                    'evaluation_timestamp': datetime.now().isoformat(),
                    'validator_uid': getattr(self, 'uid', 'unknown'),
                    'total_tasks': 0,
                    'successful_evaluations': 0,
                    'failed_evaluations': 0
                }
            
            # Record task evaluation
            evaluation_record = {
                'task_id': task_id,
                'evaluated_at': datetime.now().isoformat(),
                'validator_uid': getattr(self, 'uid', 'unknown'),
                'validator_identifier': validator_identifier,
                'task_type': validator_performance.get('task_type', 'unknown'),
                'processing_time': validator_performance.get('processing_time', 0),
                'accuracy_score': validator_performance.get('accuracy_score', 0),
                'speed_score': validator_performance.get('speed_score', 0)
            }
            
            self.evaluation_history[current_epoch]['tasks_evaluated'].append(evaluation_record)
            self.evaluation_history[current_epoch]['total_tasks'] += 1
            self.evaluation_history[current_epoch]['successful_evaluations'] += 1
            
            # Save evaluation history to disk
            self.save_evaluation_history()
            
            # Post evaluation data to proxy server
            await self.post_evaluation_data_to_proxy(task_id, validator_performance)
            
            bt.logging.info(f"✅ Task {task_id} successfully marked as evaluated by {validator_identifier}")
            
        except Exception as e:
            bt.logging.error(f"❌ Error marking task {task_id} as evaluated: {str(e)}")
            # Still add to cache to prevent re-evaluation
            self.evaluated_tasks_cache.add(task_id)
    
    async def post_evaluation_data_to_proxy(self, task_id: str, validator_performance: Dict):
        """Post evaluation data to proxy server for tracking"""
        try:
            evaluation_data = {
                'task_id': task_id,
                'validator_uid': getattr(self, 'uid', 'unknown'),
                'evaluated_at': datetime.now().isoformat(),
                'evaluation_data': validator_performance
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Convert to Form data as expected by proxy endpoint
                form_data = {
                    'task_id': task_id,
                    'validator_uid': getattr(self, 'uid', 'unknown'),
                    'evaluation_data': json.dumps(evaluation_data)
                }
                
                headers = self._get_auth_headers()
                response = await client.post(
                    f"{self.proxy_server_url}/api/v1/validator/evaluation",
                    headers=headers,
                    data=form_data,  # Use data instead of json
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    bt.logging.debug(f"✅ Evaluation data posted to proxy server for task {task_id}")
                else:
                    bt.logging.warning(f"⚠️  Failed to post evaluation data to proxy server: {response.status_code}")
                    
        except Exception as e:
            bt.logging.warning(f"⚠️  Could not post evaluation data to proxy server: {str(e)}")
    
    async def get_validator_evaluated_tasks(self) -> set:
        """Get set of task IDs already evaluated by this validator"""
        try:
            # First check in-memory cache
            if self.evaluated_tasks_cache:
                bt.logging.debug(f"📚 Found {len(self.evaluated_tasks_cache)} tasks in memory cache")
                return self.evaluated_tasks_cache.copy()
            
            # Try to get from proxy server with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    timeout = 60.0 * (attempt + 1)  # Increase timeout with each retry
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        headers = self._get_auth_headers()
                        response = await client.get(
                            f"{self.proxy_server_url}/api/v1/validator/{getattr(self, 'uid', 'unknown')}/evaluated_tasks",
                            headers=headers,
                            timeout=timeout
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            evaluated_tasks = data.get('evaluated_tasks', [])
                            
                            # Convert to set and update in-memory cache
                            evaluated_tasks_set = set(evaluated_tasks)
                            self.evaluated_tasks_cache.update(evaluated_tasks_set)
                            
                            bt.logging.info(f"📚 Retrieved {len(evaluated_tasks_set)} evaluated tasks from proxy server")
                            return evaluated_tasks_set
                        else:
                            bt.logging.warning(f"⚠️  Proxy server returned status {response.status_code} for evaluated tasks")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                            else:
                                return set()
                except (httpx.TimeoutException, httpx.RequestError) as e:
                    error_msg = str(e)
                    if isinstance(e, httpx.TimeoutException) or "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                        timeout_seconds = 60 * (attempt + 1)  # Assuming similar timeout structure
                        bt.logging.warning(f"⏰ Request timed out after {timeout_seconds}s (attempt {attempt + 1}/{max_retries})")
                        bt.logging.info(f"   The proxy server is taking longer than expected to respond.")
                    else:
                        bt.logging.warning(f"⚠️  Network error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        bt.logging.info(f"   ⏳ Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        bt.logging.error(f"❌ Failed to retrieve evaluated tasks after {max_retries} attempts")
                        bt.logging.info(f"   💡 Continuing without evaluated tasks cache - validator will use in-memory tracking")
                        return set()
                    
        except Exception as e:
            bt.logging.warning(f"⚠️  Could not retrieve evaluated tasks from proxy server: {str(e)}")
            return set()
    
    async def filter_already_evaluated_tasks(self, completed_tasks: List[Dict]) -> List[Dict]:
        """
        Filter out tasks that have already been evaluated by this validator.
        Checks both in-memory cache and database to prevent duplicate evaluation.
        """
        try:
            bt.logging.info(f"🔍 Filtering {len(completed_tasks)} completed tasks for already evaluated ones...")
            
            # Get list of already evaluated tasks from database
            evaluated_task_ids = set(await self.get_validator_evaluated_tasks())
            
            # Also check in-memory cache
            if hasattr(self, 'evaluated_tasks_cache') and self.evaluated_tasks_cache:
                evaluated_task_ids.update(self.evaluated_tasks_cache)
                bt.logging.debug(f"   Found {len(self.evaluated_tasks_cache)} tasks in memory cache")
            
            if not evaluated_task_ids:
                bt.logging.info("📋 No previously evaluated tasks found, proceeding with all tasks")
                return completed_tasks
            
            # Filter out already evaluated tasks
            new_tasks = []
            skipped_tasks = []
            
            for task in completed_tasks:
                task_id = task.get('task_id')
                if not task_id:
                    bt.logging.warning(f"⚠️  Task missing task_id, skipping: {task}")
                    continue
                    
                # Check both database and cache
                if task_id not in evaluated_task_ids and task_id not in self.evaluated_tasks_cache:
                    new_tasks.append(task)
                else:
                    skipped_tasks.append(task_id)
                    bt.logging.debug(f"⏭️  Skipping task {task_id} - already evaluated by this validator")
            
            bt.logging.info(f"📋 Filtering complete:")
            bt.logging.info(f"   Total tasks: {len(completed_tasks)}")
            bt.logging.info(f"   Already evaluated: {len(skipped_tasks)}")
            bt.logging.info(f"   New tasks for evaluation: {len(new_tasks)}")
            
            if skipped_tasks:
                bt.logging.debug(f"   Skipped task IDs: {skipped_tasks[:10]}{'...' if len(skipped_tasks) > 10 else ''}")
            
            return new_tasks
            
        except Exception as e:
            bt.logging.error(f"❌ Error filtering already evaluated tasks: {str(e)}")
            import traceback
            bt.logging.error(traceback.format_exc())
            # Return all tasks if filtering fails to prevent data loss
            return completed_tasks
    
    def log_evaluation_summary(self, epoch: int, tasks_evaluated: int, miner_performance: Dict):
        """Log comprehensive evaluation summary for the current epoch"""
        try:
            bt.logging.info("=" * 80)
            bt.logging.info(f"📊 EVALUATION SUMMARY - EPOCH {epoch}")
            bt.logging.info("=" * 80)
            
            # Epoch statistics
            bt.logging.info(f"📈 Epoch Statistics:")
            bt.logging.info(f"   Epoch Number: {epoch}")
            bt.logging.info(f"   Tasks Evaluated: {tasks_evaluated}")
            bt.logging.info(f"   Miners Participating: {len(miner_performance)}")
            bt.logging.info(f"   Evaluation Timestamp: {datetime.now().isoformat()}")
            
            # Miner performance summary
            if miner_performance:
                total_scores = [perf['total_score'] for perf in miner_performance.values()]
                avg_score = sum(total_scores) / len(total_scores)
                max_score = max(total_scores)
                min_score = min(total_scores)
                
                bt.logging.info(f"\n🏆 Miner Performance Summary:")
                bt.logging.info(f"   Average Total Score: {avg_score:.2f}")
                bt.logging.info(f"   Highest Score: {max_score:.2f}")
                bt.logging.info(f"   Lowest Score: {min_score:.2f}")
                bt.logging.info(f"   Score Range: {max_score - min_score:.2f}")
                
                # Top performers
                top_miners = sorted(miner_performance.items(), key=lambda x: x[1]['total_score'], reverse=True)[:5]
                bt.logging.info(f"\n🥇 Top 5 Performers:")
                for i, (miner_uid, performance) in enumerate(top_miners, 1):
                    bt.logging.info(f"   #{i} | UID {miner_uid:3d} | Score: {performance['total_score']:6.2f} | Tasks: {performance['task_count']:2d}")
            
            # Performance metrics summary
            performance_summary = self.get_performance_summary()
            bt.logging.info(f"\n📊 Overall Performance Metrics:")
            bt.logging.info(f"   Total Operations: {performance_summary.get('total_operations', 0)}")
            bt.logging.info(f"   Success Rate: {performance_summary.get('overall_success_rate', 0):.1f}%")
            
            # Recent errors
            recent_errors = performance_summary.get('recent_errors', [])
            if recent_errors:
                bt.logging.info(f"\n⚠️  Recent Errors ({len(recent_errors)}):")
                for error in recent_errors[-3:]:  # Last 3 errors
                    bt.logging.info(f"   {error.get('timestamp', 'Unknown')}: {error.get('error', 'Unknown error')}")
            
            bt.logging.info("=" * 80)
            
        except Exception as e:
            bt.logging.error(f"❌ Error logging evaluation summary: {str(e)}")

    def save_performance_metrics(self):
        """Save current performance metrics to disk"""
        try:
            if not self.performance_metrics:
                return
            
            # Create performance summary
            performance_summary = self.get_performance_summary()
            
            # Add current timestamp and block information
            performance_summary['block'] = getattr(self, 'block', 'unknown')
            performance_summary['epoch'] = getattr(self, 'current_epoch', 0)
            performance_summary['validator_uid'] = getattr(self, 'uid', 'unknown')
            
            # Save to JSON file
            with open(self.performance_log_path, 'w') as f:
                json.dump(performance_summary, f, indent=2, default=str)
            
            bt.logging.debug("💾 Performance metrics saved to disk")
            
        except Exception as e:
            bt.logging.warning(f"⚠️  Could not save performance metrics: {str(e)}")
    
    def cleanup_old_data(self):
        """Clean up old data to prevent memory bloat"""
        try:
            # Clean up old evaluation history (keep last 10 epochs)
            if len(self.evaluation_history) > 10:
                old_epochs = sorted(self.evaluation_history.keys())[:-10]
                for old_epoch in old_epochs:
                    del self.evaluation_history[old_epoch]
                bt.logging.debug(f"🧹 Cleaned up {len(old_epochs)} old epochs from evaluation history")
            
            # Clean up old performance metrics (keep last 1000 operations per type)
            for operation, metrics in self.performance_metrics.items():
                if 'response_times' in metrics and len(metrics['response_times']) > 1000:
                    metrics['response_times'] = metrics['response_times'][-1000:]
                if 'errors' in metrics and len(metrics['errors']) > 100:
                    metrics['errors'] = metrics['errors'][-100:]
            
            # Clean up evaluated tasks cache if it gets too large
            if len(self.evaluated_tasks_cache) > 10000:
                # Keep only recent tasks (this is a simple approach)
                # In production, you might want to implement a more sophisticated LRU cache
                bt.logging.warning(f"⚠️  Evaluated tasks cache is large ({len(self.evaluated_tasks_cache)}), consider implementing LRU cache")
            
        except Exception as e:
            bt.logging.warning(f"⚠️  Error during cleanup: {str(e)}")
    
    def get_validator_status(self) -> Dict:
        """Get comprehensive validator status for monitoring"""
        try:
            status = {
                'validator_uid': getattr(self, 'uid', 'unknown'),
                'current_block': getattr(self, 'block', 'unknown'),
                'current_epoch': getattr(self, 'current_epoch', 0),
                'step': getattr(self, 'step', 0),
                'proxy_integration_enabled': self.enable_proxy_integration,
                'proxy_server_url': self.proxy_server_url,
                'evaluation_status': {
                    'last_evaluation_block': self.last_evaluation_block,
                    'blocks_since_evaluation': getattr(self, 'block', 0) - self.last_evaluation_block if hasattr(self, 'block') else 0,
                    'evaluation_interval': self.evaluation_interval,
                    'tasks_evaluated_this_epoch': len(self.evaluated_tasks_cache)
                },
                'weight_setting_status': {
                    'last_weight_setting_block': self.last_weight_setting_block,
                    'blocks_since_weight_setting': getattr(self, 'block', 0) - self.last_weight_setting_block if hasattr(self, 'block') else 0,
                    'weight_setting_interval': self.weight_setting_interval,
                    'proxy_tasks_processed_this_epoch': self.proxy_tasks_processed_this_epoch
                },
                'miner_status': {
                    'total_miners': len(self.metagraph.hotkeys) if hasattr(self, 'metagraph') else 0,
                    'reachable_miners': len(self.reachable_miners) if hasattr(self, 'reachable_miners') else 0,
                    'top_miners_by_stake': []
                },
                'performance_metrics': self.get_performance_summary(),
                'evaluation_history': {
                    'total_epochs': len(self.evaluation_history),
                    'recent_epochs': list(self.evaluation_history.keys())[-5:] if self.evaluation_history else []
                },
                'timestamp': datetime.now().isoformat()
            }
            
            # Add top miners by stake if available
            if hasattr(self, 'reachable_miners') and self.reachable_miners:
                top_miners = sorted(self.reachable_miners, key=lambda x: self.metagraph.S[x], reverse=True)[:5]
                status['miner_status']['top_miners_by_stake'] = [
                    {'uid': uid, 'stake': float(self.metagraph.S[uid])} for uid in top_miners
                ]
            
            return status
            
        except Exception as e:
            bt.logging.error(f"❌ Error getting validator status: {str(e)}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def log_validator_status(self):
        """Log comprehensive validator status for monitoring"""
        try:
            status = self.get_validator_status()
            
            bt.logging.info("=" * 80)
            bt.logging.info("📊 VALIDATOR STATUS REPORT")
            bt.logging.info("=" * 80)
            
            # Basic info
            bt.logging.info(f"🔧 Validator Information:")
            bt.logging.info(f"   UID: {status['validator_uid']}")
            bt.logging.info(f"   Current Block: {status['current_block']}")
            bt.logging.info(f"   Current Epoch: {status['current_epoch']}")
            bt.logging.info(f"   Step: {status['step']}")
            
            # Proxy integration
            bt.logging.info(f"\n🔗 Proxy Integration:")
            bt.logging.info(f"   Enabled: {status['proxy_integration_enabled']}")
            bt.logging.info(f"   Server URL: {status['proxy_server_url']}")
            
            # Evaluation status
            eval_status = status['evaluation_status']
            bt.logging.info(f"\n🔍 Evaluation Status:")
            bt.logging.info(f"   Last Evaluation Block: {eval_status['last_evaluation_block']}")
            bt.logging.info(f"   Blocks Since Evaluation: {eval_status['blocks_since_evaluation']}")
            bt.logging.info(f"   Evaluation Interval: {eval_status['evaluation_interval']}")
            bt.logging.info(f"   Tasks Evaluated This Epoch: {eval_status['tasks_evaluated_this_epoch']}")
            
            # Weight setting status
            weight_status = status['weight_setting_status']
            bt.logging.info(f"\n⚖️  Weight Setting Status:")
            bt.logging.info(f"   Last Weight Setting Block: {weight_status['last_weight_setting_block']}")
            bt.logging.info(f"   Blocks Since Weight Setting: {weight_status['blocks_since_weight_setting']}")
            bt.logging.info(f"   Weight Setting Interval: {weight_status['weight_setting_interval']}")
            bt.logging.info(f"   Proxy Tasks Processed This Epoch: {weight_status['proxy_tasks_processed_this_epoch']}")
            
            # Miner status
            miner_status = status['miner_status']
            bt.logging.info(f"\n👥 Miner Status:")
            bt.logging.info(f"   Total Miners: {miner_status['total_miners']}")
            bt.logging.info(f"   Reachable Miners: {miner_status['reachable_miners']}")
            
            if miner_status['top_miners_by_stake']:
                bt.logging.info(f"   Top Miners by Stake:")
                for i, miner in enumerate(miner_status['top_miners_by_stake'][:3], 1):
                    bt.logging.info(f"      #{i} | UID {miner['uid']:3d} | Stake: {miner['stake']:,.0f} TAO")
            
            # Performance summary
            perf_summary = status['performance_metrics']
            bt.logging.info(f"\n📈 Performance Summary:")
            bt.logging.info(f"   Total Operations: {perf_summary.get('total_operations', 0)}")
            bt.logging.info(f"   Overall Success Rate: {perf_summary.get('overall_success_rate', 0):.1f}%")
            
            # Evaluation history
            eval_history = status['evaluation_history']
            bt.logging.info(f"\n📚 Evaluation History:")
            bt.logging.info(f"   Total Epochs: {eval_history['total_epochs']}")
            bt.logging.info(f"   Recent Epochs: {eval_history['recent_epochs']}")
            
            bt.logging.info("=" * 80)
            
        except Exception as e:
            bt.logging.error(f"❌ Error logging validator status: {str(e)}")
    
    def periodic_maintenance(self):
        """Perform periodic maintenance tasks"""
        try:
            # Save performance metrics
            self.save_performance_metrics()
            
            # Clean up old data
            self.cleanup_old_data()
            
            # Log status every 50 blocks
            if hasattr(self, 'step') and self.step % 50 == 0:
                self.log_validator_status()
            
            bt.logging.debug("🔧 Periodic maintenance completed")
            
        except Exception as e:
            bt.logging.warning(f"⚠️  Error during periodic maintenance: {str(e)}")

    def set_weights(self):
        """
        Override the base validator's set_weights method to only set weights for active miners.
        This prevents the default behavior of setting equal weights for all miners.
        
        Returns:
            bool: True if weights were successfully set on blockchain, False otherwise
        """
        try:
            bt.logging.info("🎯 Setting weights ONLY for active miners...")
            
            # CRITICAL FIX: Calculate scores from miner performance data if not available
            if not hasattr(self, 'scores') or self.scores is None:
                bt.logging.info("🔄 No scores available - calculating from miner performance data...")
                
                # Initialize scores array with zeros
                if hasattr(self, 'metagraph') and self.metagraph.n > 0:
                    self.scores = np.zeros(self.metagraph.n)
                else:
                    bt.logging.warning("⚠️ No metagraph available - cannot calculate scores")
                    return False
            
            # CRITICAL FIX: Update scores from miner performance data
            if hasattr(self, 'miner_performance') and self.miner_performance:
                bt.logging.info(f"📊 Updating scores from {len(self.miner_performance)} miner performance records...")
                
                for miner_uid, performance in self.miner_performance.items():
                    if miner_uid < len(self.scores):
                        # Convert performance score to 0-1 range
                        total_score = performance.get('total_score', 0)
                        if total_score > 0:
                            # Normalize to 0-1 range (assuming max score is 500)
                            normalized_score = min(total_score / 500.0, 1.0)
                            self.scores[miner_uid] = normalized_score
                            bt.logging.info(f"   UID {miner_uid}: score = {normalized_score:.6f} (from {total_score:.2f})")
                
                bt.logging.info(f"✅ Updated scores for {np.sum(self.scores > 0)} miners")
            else:
                bt.logging.warning("⚠️ No miner performance data available - using existing scores")
            
            # Check if we have scores set
            if not hasattr(self, 'scores') or self.scores is None:
                bt.logging.warning("⚠️ No scores available - skipping weight setting")
                return False
            
            # Find only the UIDs with non-zero scores (active miners)
            active_uids = np.where(self.scores > 0)[0]
            active_weights = self.scores[active_uids]
            
            if len(active_uids) == 0:
                bt.logging.warning("⚠️ No active miners with scores > 0 - skipping weight setting")
                return False
            
            bt.logging.info(f"📊 Setting weights for {len(active_uids)} active miners:")
            for i, uid in enumerate(active_uids):
                bt.logging.info(f"   UID {uid}: weight = {active_weights[i]:.6f}")
            
            # Normalize weights to sum to 1.0
            total_weight = np.sum(active_weights)
            if total_weight > 0:
                normalized_weights = active_weights / total_weight
            else:
                bt.logging.warning("⚠️ Total weight is 0 - cannot normalize")
                return False
            
            bt.logging.info(f"📊 Normalized weights sum: {np.sum(normalized_weights):.6f}")
            
            # Convert to uint16 weights and uids for blockchain submission
            from template.base.utils.weight_utils import convert_weights_and_uids_for_emit
            
            uint_uids, uint_weights = convert_weights_and_uids_for_emit(
                uids=active_uids, 
                weights=normalized_weights
            )
            
            bt.logging.info(f"🔗 Submitting weights to blockchain for {len(uint_uids)} miners...")
            
            # Set the weights on chain via our subtensor connection
            result, msg = self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.config.netuid,
                uids=uint_uids,
                weights=uint_weights,
                wait_for_finalization=False,
                wait_for_inclusion=False,
                version_key=self.spec_version,
            )
            
            if result is True:
                bt.logging.info("✅ Weights set on blockchain successfully!")
                bt.logging.info(f"   Active miners: {len(active_uids)}")
                bt.logging.info(f"   Total miners in network: {self.metagraph.n}")
                bt.logging.info(f"   Efficiency: {len(active_uids)}/{len(active_uids)}/{self.metagraph.n} miners rewarded")
                
                # CRITICAL FIX: Update timestamp of last successful weight commit
                self.last_weight_commit_timestamp = time.time()
                bt.logging.info(f"   ⏰ Weight commit timestamp updated: {self.last_weight_commit_timestamp:.0f}")
                
                return True
            else:
                bt.logging.error(f"❌ set_weights failed: {msg}")
                return False
                
        except Exception as e:
            bt.logging.error(f"❌ Error in custom set_weights: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


# The main function parses the configuration and runs the validator.
if __name__ == "__main__":
    import argparse
    
    # Create argument parser
    parser = argparse.ArgumentParser(description="Bittensor Audio Processing Validator")
    parser.add_argument("--proxy_server_url", type=str, default="https://violet-proxy-bl4w.onrender.com",
                       help="URL of the proxy server for task integration")
    parser.add_argument("--enable_proxy_integration", action="store_true", default=True,
                       help="Enable integration with proxy server")
    parser.add_argument("--proxy_check_interval", type=int, default=30,
                       help="Interval in seconds to check proxy server for tasks")
    
    # Parse arguments
    args, unknown = parser.parse_known_args()
    
    # Store proxy config in environment variables for the validator to access
    import os
    os.environ['PROXY_SERVER_URL'] = args.proxy_server_url
    os.environ['ENABLE_PROXY_INTEGRATION'] = str(args.enable_proxy_integration)
    os.environ['PROXY_CHECK_INTERVAL'] = str(args.proxy_check_interval)
    
    with Validator() as validator:
        bt.logging.info("🚀 Validator started with proxy server integration")
        bt.logging.info(f"🔗 Proxy server URL: {args.proxy_server_url}")
        bt.logging.info(f"⏱️  Check interval: {args.proxy_check_interval}s")
        
        while True:
            # Log less frequently to reduce console spam
            if int(time.time()) % 60 == 0:  # Only log every minute
                bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
