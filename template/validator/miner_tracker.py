# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# TODO(developer): Set your name
# Copyright © 2023 <your name>

import time
import json
import asyncio
import os
import shutil
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import bittensor as bt
import numpy as np


@dataclass
class MinerMetrics:
    """Track individual miner performance metrics"""
    uid: int
    hotkey: str
    stake: float
    
    # Performance metrics
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    
    # Recent performance (last 50 tasks)
    recent_response_times: deque = None
    recent_success_rate: float = 1.0
    
    # Load tracking
    current_load: int = 0  # Number of active tasks
    max_concurrent_tasks: int = 5  # Miner's capacity
    
    # Task type specialization
    task_type_performance: Dict[str, Dict] = None
    
    # Timestamps
    last_seen: float = 0.0
    first_seen: float = 0.0
    
    def __post_init__(self):
        if self.recent_response_times is None:
            self.recent_response_times = deque(maxlen=50)
        if self.task_type_performance is None:
            self.task_type_performance = defaultdict(lambda: {
                'total': 0,
                'successful': 0,
                'avg_time': 0.0,
                'success_rate': 1.0
            })
        if self.first_seen == 0.0:
            self.first_seen = time.time()
    
    def update_task_completion(self, task_type: str, success: bool, processing_time: float):
        """Update metrics after task completion"""
        self.total_tasks += 1
        self.current_load = max(0, self.current_load - 1)  # Reduce load
        
        if success:
            self.successful_tasks += 1
        else:
            self.failed_tasks += 1
        
        # Update processing time metrics
        self.total_processing_time += processing_time
        self.average_processing_time = self.total_processing_time / self.total_tasks
        
        # Update recent response times
        self.recent_response_times.append(processing_time)
        
        # Update recent success rate (last 50 tasks)
        if len(self.recent_response_times) >= 10:
            recent_tasks = min(50, self.total_tasks)
            recent_successful = self.successful_tasks - max(0, self.total_tasks - recent_tasks)
            self.recent_success_rate = recent_successful / recent_tasks
        
        # Update task type performance
        task_perf = self.task_type_performance[task_type]
        task_perf['total'] += 1
        if success:
            task_perf['successful'] += 1
        
        # Update average time for this task type
        if task_perf['total'] > 0:
            task_perf['avg_time'] = (task_perf['avg_time'] * (task_perf['total'] - 1) + processing_time) / task_perf['total']
            task_perf['success_rate'] = task_perf['successful'] / task_perf['total']
        
        self.last_seen = time.time()
    
    def assign_task(self, task_type: str) -> bool:
        """Check if miner can accept a new task"""
        if self.current_load >= self.max_concurrent_tasks:
            return False
        
        self.current_load += 1
        return True
    
    def get_performance_score(self, task_type: str = None) -> float:
        """Calculate overall performance score (0-1)"""
        if self.total_tasks == 0:
            return 0.5  # Neutral score for new miners
        
        # Base success rate
        success_rate = self.successful_tasks / self.total_tasks
        
        # Speed score (faster = better)
        speed_score = max(0, 1 - (self.average_processing_time / 30))  # 30s baseline
        
        # Recent performance bonus
        recent_bonus = self.recent_success_rate * 0.2
        
        # Task type specialization bonus
        specialization_bonus = 0.0
        if task_type and task_type in self.task_type_performance:
            task_perf = self.task_type_performance[task_type]
            if task_perf['total'] >= 5:  # Need minimum samples
                specialization_bonus = task_perf['success_rate'] * 0.1
        
        # Load penalty (overloaded miners get penalized)
        load_penalty = max(0, (self.current_load / self.max_concurrent_tasks) * 0.1)
        
        final_score = (success_rate * 0.4 + 
                      speed_score * 0.3 + 
                      recent_bonus + 
                      specialization_bonus - 
                      load_penalty)
        
        return max(0.0, min(1.0, final_score))
    
    def get_availability_score(self) -> float:
        """Calculate availability score based on current load"""
        if self.current_load >= self.max_concurrent_tasks:
            return 0.0
        
        # More available = higher score
        availability = 1 - (self.current_load / self.max_concurrent_tasks)
        return availability
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['recent_response_times'] = list(self.recent_response_times)
        # Don't include computed scores in storage
        return data


class MinerTracker:
    """Track and manage miner performance, load, and availability"""
    
    def __init__(self, config):
        self.config = config
        self.miners: Dict[int, MinerMetrics] = {}
        self.task_queue: List[Dict] = []
        self.metrics_file = "miner_metrics.json"
        self.load_balancing_enabled = True
        self.min_miners_per_task = 3
        self.max_miners_per_task = 5
        
        # Load existing metrics if available
        self.load_metrics()
    
    def load_metrics(self):
        """Load miner metrics from file with robust error handling"""
        try:
            # Check if file exists and is readable
            if not os.path.exists(self.metrics_file):
                bt.logging.info("📁 No existing metrics file found, starting fresh")
                return
            
            # Check file size - if too small or empty, skip
            if os.path.getsize(self.metrics_file) < 10:
                bt.logging.info("📁 Metrics file is empty or too small, starting fresh")
                return
            
            with open(self.metrics_file, 'r') as f:
                content = f.read().strip()
                
                # Check if file is empty or just whitespace
                if not content:
                    bt.logging.info("📁 Metrics file is empty, starting fresh")
                    return
                
                # Try to parse JSON
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as json_err:
                    # Log at debug level since we're handling it gracefully
                    bt.logging.debug(
                        f"Corrupted metrics file detected (JSON error at line {json_err.lineno}): {json_err.msg}"
                    )
                    bt.logging.info(f"📁 Corrupted metrics file detected, backing up and starting fresh")
                    # Backup corrupted file
                    backup_file = f"{self.metrics_file}.corrupted.{int(time.time())}"
                    try:
                        os.rename(self.metrics_file, backup_file)
                        bt.logging.debug(f"   Corrupted file backed up to: {backup_file}")
                    except Exception as backup_err:
                        # If rename fails, try to delete the corrupted file
                        try:
                            os.remove(self.metrics_file)
                            bt.logging.debug(f"   Deleted corrupted file (backup failed)")
                        except:
                            pass
                    return
                
                # Validate data structure
                if not isinstance(data, dict):
                    bt.logging.warning(f"⚠️  Invalid metrics file format, expected dict, got {type(data)}")
                    return
                
                # Load miner data
                loaded_count = 0
                for uid_str, miner_data in data.items():
                    try:
                        uid = int(uid_str)
                        if not isinstance(miner_data, dict):
                            bt.logging.debug(f"⚠️  Skipping invalid miner data for UID {uid_str}")
                            continue
                        
                        miner = MinerMetrics(**miner_data)
                        # Convert list back to deque
                        if 'recent_response_times' in miner_data and isinstance(miner_data['recent_response_times'], list):
                            miner.recent_response_times = deque(
                                miner_data['recent_response_times'], 
                                maxlen=50
                            )
                        self.miners[uid] = miner
                        loaded_count += 1
                    except Exception as e:
                        bt.logging.debug(f"⚠️  Skipping invalid miner data for UID {uid_str}: {e}")
                        continue
                
                if loaded_count > 0:
                    bt.logging.info(f"✅ Loaded metrics for {loaded_count} miners")
                else:
                    bt.logging.info("📁 No valid miner data in metrics file, starting fresh")
                    
        except FileNotFoundError:
            bt.logging.info("📁 No existing metrics file found, starting fresh")
        except Exception as e:
            # Log at info level with clear message that it's being handled
            bt.logging.info(f"📁 Metrics file issue detected: {e}")
            bt.logging.info(f"   Starting with fresh metrics file")
            # Try to backup/delete corrupted file
            try:
                if os.path.exists(self.metrics_file):
                    backup_file = f"{self.metrics_file}.error.{int(time.time())}"
                    try:
                        os.rename(self.metrics_file, backup_file)
                        bt.logging.debug(f"   Error file backed up to: {backup_file}")
                    except:
                        # If rename fails, try to delete
                        try:
                            os.remove(self.metrics_file)
                            bt.logging.debug(f"   Deleted corrupted file")
                        except:
                            pass
            except:
                pass
    
    def save_metrics(self):
        """Save miner metrics to file with validation"""
        try:
            data = {str(uid): miner.to_dict() for uid, miner in self.miners.items()}
            
            # Validate data before saving (prevent corruption)
            try:
                # Try to serialize to ensure it's valid JSON
                json_str = json.dumps(data, indent=2)
                # Try to parse it back to ensure it's valid
                json.loads(json_str)
            except Exception as validation_err:
                bt.logging.error(f"❌ Invalid data structure, skipping save: {validation_err}")
                return
            
            # Write to temporary file first, then rename (atomic write)
            temp_file = f"{self.metrics_file}.tmp"
            with open(temp_file, 'w') as f:
                f.write(json_str)
            
            # Atomic rename (prevents corruption if process crashes during write)
            shutil.move(temp_file, self.metrics_file)
            
            bt.logging.debug(f"💾 Saved metrics for {len(self.miners)} miners")
        except Exception as e:
            bt.logging.error(f"❌ Failed to save metrics: {e}")
            # Clean up temp file if it exists
            try:
                temp_file = f"{self.metrics_file}.tmp"
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
    
    def register_miner(self, uid: int, hotkey: str, stake: float):
        """Register a new miner or update existing one"""
        if uid not in self.miners:
            self.miners[uid] = MinerMetrics(uid=uid, hotkey=hotkey, stake=stake)
            bt.logging.info(f"🆕 Registered new miner UID {uid}")
        else:
            # Update existing miner info
            self.miners[uid].hotkey = hotkey
            self.miners[uid].stake = stake
            self.miners[uid].last_seen = time.time()
    
    def get_available_miners(self, task_type: str = None, min_count: int = None) -> List[int]:
        """Get list of available miners for task assignment"""
        if min_count is None:
            min_count = self.min_miners_per_task
        
        available = []
        for uid, miner in self.miners.items():
            if miner.current_load < miner.max_concurrent_tasks:
                available.append(uid)
        
        if len(available) < min_count:
            bt.logging.warning(f"⚠️  Only {len(available)} miners available, need {min_count}")
            return available
        
        return available
    
    def select_miners_for_task(self, task_type: str, required_count: int = None) -> List[int]:
        """Intelligently select miners for a specific task"""
        if required_count is None:
            required_count = self.min_miners_per_task
        
        available_miners = self.get_available_miners(task_type, required_count)
        
        if len(available_miners) < required_count:
            bt.logging.warning(f"⚠️  Insufficient miners: {len(available_miners)} < {required_count}")
            return available_miners
        
        # Calculate composite scores for each miner
        miner_scores = []
        for uid in available_miners:
            miner = self.miners[uid]
            
            # Stake score (30%)
            stake_score = miner.stake / max(m.stake for m in self.miners.values()) if self.miners else 0
            
            # Performance score (40%)
            performance_score = miner.get_performance_score(task_type)
            
            # Availability score (20%)
            availability_score = miner.get_availability_score()
            
            # Specialization bonus (10%)
            specialization_bonus = 0.0
            if task_type in miner.task_type_performance:
                task_perf = miner.task_type_performance[task_type]
                if task_perf['total'] >= 3:  # Minimum samples for specialization
                    specialization_bonus = task_perf['success_rate'] * 0.1
            
            # Composite score
            composite_score = (stake_score * 0.3 + 
                             performance_score * 0.4 + 
                             availability_score * 0.2 + 
                             specialization_bonus)
            
            miner_scores.append((uid, composite_score))
        
        # Sort by score and select top miners
        miner_scores.sort(key=lambda x: x[1], reverse=True)
        selected_uids = [uid for uid, score in miner_scores[:required_count]]
        
        # Assign tasks to selected miners
        for uid in selected_uids:
            self.miners[uid].assign_task(task_type)
        
        bt.logging.debug(f"🎯 Selected {len(selected_uids)} miners for {task_type}: {selected_uids}")
        return selected_uids
    
    def update_task_result(self, uid: int, task_type: str, success: bool, processing_time: float):
        """Update miner metrics after task completion"""
        if uid in self.miners:
            self.miners[uid].update_task_completion(task_type, success, processing_time)
            bt.logging.debug(f"📊 Updated metrics for UID {uid}: success={success}, time={processing_time:.2f}s")
        else:
            bt.logging.warning(f"⚠️  Unknown miner UID {uid} in task result")
    
    def get_miner_stats(self) -> Dict:
        """Get overall statistics about all miners"""
        if not self.miners:
            return {}
        
        total_miners = len(self.miners)
        available_miners = len([m for m in self.miners.values() if m.current_load < m.max_concurrent_tasks])
        
        # Performance statistics
        avg_success_rate = np.mean([m.successful_tasks / max(m.total_tasks, 1) for m in self.miners.values()])
        avg_processing_time = np.mean([m.average_processing_time for m in self.miners.values() if m.total_tasks > 0])
        
        # Load distribution
        load_distribution = defaultdict(int)
        for miner in self.miners.values():
            load_distribution[miner.current_load] += 1
        
        return {
            'total_miners': total_miners,
            'available_miners': available_miners,
            'average_success_rate': avg_success_rate,
            'average_processing_time': avg_processing_time,
            'load_distribution': dict(load_distribution),
            'total_tasks_processed': sum(m.total_tasks for m in self.miners.values())
        }
    
    def cleanup_old_miners(self, max_age_hours: int = 24):
        """Remove miners that haven't been seen recently"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        removed_count = 0
        for uid in list(self.miners.keys()):
            miner = self.miners[uid]
            if current_time - miner.last_seen > max_age_seconds:
                del self.miners[uid]
                removed_count += 1
        
        if removed_count > 0:
            bt.logging.debug(f"🧹 Cleaned up {removed_count} inactive miners")
            self.save_metrics()
    
    def get_performance_ranking(self, task_type: str = None) -> List[Tuple[int, float]]:
        """Get ranked list of miners by performance"""
        rankings = []
        for uid, miner in self.miners.items():
            score = miner.get_performance_score(task_type)
            rankings.append((uid, score))
        
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings
    
    def print_miner_summary(self):
        """Print summary of all miners (concise version)"""
        if not self.miners:
            bt.logging.info("📊 No miners registered")
            return
        
        # Sort by performance score
        rankings = self.get_performance_ranking()
        
        # Show only top 5 miners with concise info
        bt.logging.info(f"📊 Top 5 miners by performance:")
        for rank, (uid, score) in enumerate(rankings[:5], 1):
            miner = self.miners[uid]
            success_rate = miner.successful_tasks / max(miner.total_tasks, 1)
            bt.logging.info(f"{rank}. UID {uid:3d} | Score: {score:.3f} | Success: {success_rate:.1%} | Load: {miner.current_load}")
        
        # Overall stats (concise)
        stats = self.get_miner_stats()
        bt.logging.info(f"📈 Total: {stats['total_miners']} miners, {stats['available_miners']} available")
