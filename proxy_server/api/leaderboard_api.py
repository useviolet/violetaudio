"""
Leaderboard API
Provides comprehensive miner leaderboard with all metrics and rankings.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from database.postgresql_adapter import PostgreSQLAdapter
from database.postgresql_schema import MinerMetrics, Task, MinerStatus
from sqlalchemy import func, and_


class LeaderboardAPI:
    """API for generating miner leaderboards"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_leaderboard(
        self,
        limit: int = 100,
        sort_by: str = "overall_score",
        order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """
        Get comprehensive miner leaderboard with all metrics.
        
        Args:
            limit: Maximum number of miners to return
            sort_by: Field to sort by (overall_score, uptime_score, invocation_count, etc.)
            order: Sort order (asc or desc)
        
        Returns:
            List of miner leaderboard entries with all metrics
        """
        try:
            if not isinstance(self.db, PostgreSQLAdapter):
                return []
            
            session = self.db._get_session()
            try:
                # Get all miner metrics
                all_metrics = session.query(MinerMetrics).all()
                
                # Get task counts per miner
                task_counts = await self._get_task_counts_per_miner(session)
                
                # Get miner status info
                status_info = await self._get_miner_status_info(session)
                
                # Build leaderboard entries
                leaderboard = []
                for metrics in all_metrics:
                    entry = await self._build_leaderboard_entry(
                        metrics, task_counts, status_info
                    )
                    if entry:
                        leaderboard.append(entry)
                
                # Sort leaderboard
                reverse = (order.lower() == "desc")
                leaderboard.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
                
                # Add rank
                for rank, entry in enumerate(leaderboard[:limit], 1):
                    entry['rank'] = rank
                
                return leaderboard[:limit]
                
            finally:
                session.close()
                
        except Exception as e:
            print(f"❌ Error getting leaderboard: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _get_task_counts_per_miner(self, session) -> Dict[str, Dict[str, int]]:
        """Get task counts per miner (completed, assigned, total)"""
        try:
            task_counts = {}
            
            # Get all tasks with miner responses
            all_tasks = session.query(Task).all()
            
            for task in all_tasks:
                # Get assigned miners
                assigned_miners = task.assigned_miners or []
                
                # Get miner responses
                miner_responses = task.miner_responses or []
                if isinstance(miner_responses, str):
                    import json
                    try:
                        miner_responses = json.loads(miner_responses)
                    except:
                        miner_responses = []
                
                # Count responses per miner
                responded_miners = set()
                if isinstance(miner_responses, list):
                    for response in miner_responses:
                        miner_uid = response.get('miner_uid') if isinstance(response, dict) else None
                        if miner_uid:
                            responded_miners.add(miner_uid)
                
                # Update counts for each assigned miner (use UID as key)
                for miner_uid in assigned_miners:
                    if miner_uid not in task_counts:
                        task_counts[miner_uid] = {
                            'total_assigned': 0,
                            'total_completed': 0,
                            'total_responses': 0
                        }
                    
                    task_counts[miner_uid]['total_assigned'] += 1
                    
                    if miner_uid in responded_miners:
                        task_counts[miner_uid]['total_completed'] += 1
                        task_counts[miner_uid]['total_responses'] += 1
                
                # Also count responses for miners not in assigned list (edge case)
                for miner_uid in responded_miners:
                    if miner_uid not in assigned_miners:
                        if miner_uid not in task_counts:
                            task_counts[miner_uid] = {
                                'total_assigned': 0,
                                'total_completed': 0,
                                'total_responses': 0
                            }
                        task_counts[miner_uid]['total_responses'] += 1
            
            return task_counts
            
        except Exception as e:
            print(f"❌ Error getting task counts: {e}")
            return {}
    
    async def _get_miner_status_info(self, session) -> Dict[int, Dict[str, Any]]:
        """Get current miner status information"""
        try:
            status_info = {}
            miners = session.query(MinerStatus).all()
            
            for miner in miners:
                status_info[miner.uid] = {
                    'is_serving': miner.is_serving,
                    'stake': miner.stake,
                    'performance_score': miner.performance_score,
                    'current_load': miner.current_load,
                    'max_capacity': miner.max_capacity,
                    'last_seen': miner.last_seen.isoformat() if miner.last_seen else None
                }
            
            return status_info
            
        except Exception as e:
            print(f"❌ Error getting miner status: {e}")
            return {}
    
    async def _build_leaderboard_entry(
        self,
        metrics: MinerMetrics,
        task_counts: Dict[str, Dict[str, int]],
        status_info: Dict[int, Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Build a leaderboard entry for a miner"""
        try:
            # Get task counts for this miner (by UID)
            counts = task_counts.get(metrics.uid, {
                'total_assigned': 0,
                'total_completed': 0,
                'total_responses': 0
            })
            
            # Get status info
            status = status_info.get(metrics.uid, {})
            
            # Calculate overall performance score
            # Weighted: 55% uptime, 25% invocation, 15% diversity, 5% bounty
            overall_score = (
                metrics.uptime_score * 0.55 +
                metrics.invocation_score * 0.25 +
                metrics.diversity_score * 0.15 +
                metrics.bounty_score * 0.05
            )
            
            # Build entry
            entry = {
                # Identity
                'uid': metrics.uid,
                'hotkey': metrics.hotkey,
                'coldkey': metrics.coldkey,
                'miner_identity': metrics.miner_identity,
                
                # Overall performance
                'overall_score': round(overall_score, 4),
                'rank': 0,  # Will be set after sorting
                
                # Uptime metrics (55% weight)
                'uptime_score': round(metrics.uptime_score, 4),
                'uptime_percentage': round(metrics.uptime_percentage, 2),
                'uptime_seconds': round(metrics.uptime_seconds, 2),
                'total_uptime_periods': metrics.total_uptime_periods,
                
                # Invocation metrics (25% weight)
                'invocation_count': metrics.invocation_count,
                'invocation_score': round(metrics.invocation_score, 4),
                
                # Diversity metrics (15% weight)
                'diversity_count': metrics.diversity_count,
                'diversity_score': round(metrics.diversity_score, 4),
                'diversity_tasks': metrics.diversity_tasks or [],
                'diversity_models': metrics.diversity_models or [],
                
                # Bounty metrics (5% weight)
                'bounty_count': metrics.bounty_count,
                'bounty_score': round(metrics.bounty_score, 4),
                
                # Response speed
                'response_count': metrics.response_count,
                'average_response_time': round(metrics.average_response_time, 2) if metrics.average_response_time else 0.0,
                'total_response_time': round(metrics.total_response_time, 2),
                
                # Task statistics
                'total_tasks_assigned': counts['total_assigned'],
                'total_tasks_completed': counts['total_completed'],
                'total_responses_submitted': counts['total_responses'],
                'completion_rate': round(
                    (counts['total_completed'] / counts['total_assigned'] * 100) 
                    if counts['total_assigned'] > 0 else 0, 2
                ),
                
                # Current status
                'is_serving': status.get('is_serving', False),
                'stake': round(status.get('stake', 0.0), 2),
                'performance_score': round(status.get('performance_score', 0.0), 4),
                'current_load': round(status.get('current_load', 0.0), 2),
                'max_capacity': round(status.get('max_capacity', 0.0), 2),
                'load_percentage': round(
                    (status.get('current_load', 0.0) / status.get('max_capacity', 1.0) * 100)
                    if status.get('max_capacity', 0) > 0 else 0, 2
                ),
                'last_seen': status.get('last_seen'),
                
                # Timestamps
                'first_seen': metrics.first_seen.isoformat() if metrics.first_seen else None,
                'last_updated': metrics.last_updated.isoformat() if metrics.last_updated else None,
                'uid_assigned_at': metrics.uid_assigned_at.isoformat() if metrics.uid_assigned_at else None,
            }
            
            return entry
            
        except Exception as e:
            print(f"❌ Error building leaderboard entry for miner {metrics.uid}: {e}")
            return None

