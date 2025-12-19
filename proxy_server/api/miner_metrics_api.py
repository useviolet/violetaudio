"""
Centralized Miner Metrics API
Provides unified access to miner metrics for all validators.
This ensures all validators use the same metrics for fair and uniform rewards.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from database.postgresql_adapter import PostgreSQLAdapter
from database.postgresql_schema import MinerMetrics, MinerStatus
from sqlalchemy import func


class MinerMetricsAPI:
    """Centralized API for miner metrics - single source of truth for all validators"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_miner_metrics(self, miner_uid: int, hotkey: str = None) -> Optional[Dict]:
        """
        Get miner metrics by UID and hotkey (handles UID reuse).
        This is the SINGLE SOURCE OF TRUTH for all validators.
        """
        try:
            if not isinstance(self.db, PostgreSQLAdapter):
                return None
            
            session = self.db._get_session()
            try:
                # Get miner identity
                miner_identity = f"{hotkey}_{miner_uid}" if hotkey else None
                
                # Query by miner_identity if available, otherwise by UID
                if miner_identity:
                    metrics = session.query(MinerMetrics).filter(
                        MinerMetrics.miner_identity == miner_identity
                    ).first()
                else:
                    metrics = session.query(MinerMetrics).filter(
                        MinerMetrics.uid == miner_uid
                    ).first()
                
                if not metrics:
                    return None
                
                # Verify UID and hotkey still match (handle UID reuse)
                if metrics.uid != miner_uid or (hotkey and metrics.hotkey != hotkey):
                    # UID was reused - return None to create new metrics
                    return None
                
                return {
                    'uid': metrics.uid,
                    'hotkey': metrics.hotkey,
                    'coldkey': metrics.coldkey,
                    'miner_identity': metrics.miner_identity,
                    'uptime_score': metrics.uptime_score,
                    'uptime_percentage': metrics.uptime_percentage,
                    'uptime_seconds': metrics.uptime_seconds,
                    'total_uptime_periods': metrics.total_uptime_periods,
                    'invocation_count': metrics.invocation_count,
                    'invocation_score': metrics.invocation_score,
                    'diversity_count': metrics.diversity_count,
                    'diversity_tasks': metrics.diversity_tasks or [],
                    'diversity_models': metrics.diversity_models or [],
                    'diversity_score': metrics.diversity_score,
                    'bounty_count': metrics.bounty_count,
                    'bounty_score': metrics.bounty_score,
                    'total_response_time': metrics.total_response_time,
                    'response_count': metrics.response_count,
                    'average_response_time': metrics.average_response_time,
                    'first_seen': metrics.first_seen.isoformat() if metrics.first_seen else None,
                    'last_updated': metrics.last_updated.isoformat() if metrics.last_updated else None,
                    'uid_assigned_at': metrics.uid_assigned_at.isoformat() if metrics.uid_assigned_at else None,
                    'last_uid_verification': metrics.last_uid_verification.isoformat() if metrics.last_uid_verification else None,
                }
            finally:
                session.close()
        except Exception as e:
            print(f"❌ Error getting miner metrics: {e}")
            return None
    
    async def get_all_miner_metrics(self) -> List[Dict]:
        """Get metrics for all miners"""
        try:
            if not isinstance(self.db, PostgreSQLAdapter):
                return []
            
            session = self.db._get_session()
            try:
                all_metrics = session.query(MinerMetrics).all()
                return [await self._metrics_to_dict(m) for m in all_metrics]
            finally:
                session.close()
        except Exception as e:
            print(f"❌ Error getting all miner metrics: {e}")
            return []
    
    async def _metrics_to_dict(self, metrics: MinerMetrics) -> Dict:
        """Convert MinerMetrics object to dictionary"""
        return {
            'uid': metrics.uid,
            'hotkey': metrics.hotkey,
            'miner_identity': metrics.miner_identity,
            'uptime_score': metrics.uptime_score,
            'uptime_percentage': metrics.uptime_percentage,
            'invocation_count': metrics.invocation_count,
            'invocation_score': metrics.invocation_score,
            'diversity_count': metrics.diversity_count,
            'diversity_score': metrics.diversity_score,
            'bounty_count': metrics.bounty_count,
            'bounty_score': metrics.bounty_score,
            'average_response_time': metrics.average_response_time,
        }
    
    async def update_miner_metrics(
        self,
        miner_uid: int,
        hotkey: str,
        coldkey: str = None,
        **updates
    ) -> bool:
        """
        Update miner metrics (creates if doesn't exist).
        Handles UID reuse by creating new entry if hotkey changed.
        """
        try:
            if not isinstance(self.db, PostgreSQLAdapter):
                return False
            
            session = self.db._get_session()
            try:
                miner_identity = f"{hotkey}_{miner_uid}"
                
                # Check if metrics exist
                metrics = session.query(MinerMetrics).filter(
                    MinerMetrics.miner_identity == miner_identity
                ).first()
                
                if not metrics:
                    # Check if UID exists with different hotkey (UID reuse)
                    existing_uid = session.query(MinerMetrics).filter(
                        MinerMetrics.uid == miner_uid
                    ).first()
                    
                    if existing_uid and existing_uid.hotkey != hotkey:
                        print(f"⚠️ UID reuse detected: UID {miner_uid} was {existing_uid.hotkey}, now {hotkey}")
                        # Create new entry for new miner
                        metrics = MinerMetrics(
                            uid=miner_uid,
                            hotkey=hotkey,
                            coldkey=coldkey,
                            miner_identity=miner_identity,
                            uid_assigned_at=datetime.utcnow(),
                            last_uid_verification=datetime.utcnow()
                        )
                        session.add(metrics)
                    else:
                        # New miner, create fresh metrics
                        metrics = MinerMetrics(
                            uid=miner_uid,
                            hotkey=hotkey,
                            coldkey=coldkey,
                            miner_identity=miner_identity,
                            uid_assigned_at=datetime.utcnow(),
                            last_uid_verification=datetime.utcnow()
                        )
                        session.add(metrics)
                else:
                    # Verify UID still matches
                    if metrics.uid != miner_uid or metrics.hotkey != hotkey:
                        print(f"⚠️ UID/hotkey mismatch detected for {miner_identity}")
                        return False
                    
                    metrics.last_uid_verification = datetime.utcnow()
                
                # Update metrics fields
                for key, value in updates.items():
                    if hasattr(metrics, key):
                        setattr(metrics, key, value)
                
                metrics.last_updated = datetime.utcnow()
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"❌ Error updating miner metrics: {e}")
                return False
            finally:
                session.close()
        except Exception as e:
            print(f"❌ Error in update_miner_metrics: {e}")
            return False
    
    async def update_uptime(self, miner_uid: int, hotkey: str, is_online: bool, period_seconds: float = 300):
        """
        Update miner uptime based on validator reports.
        period_seconds: How long the miner was in this state (default 5 minutes)
        """
        try:
            if not isinstance(self.db, PostgreSQLAdapter):
                return False
            
            session = self.db._get_session()
            try:
                miner_identity = f"{hotkey}_{miner_uid}"
                metrics = session.query(MinerMetrics).filter(
                    MinerMetrics.miner_identity == miner_identity
                ).first()
                
                if not metrics:
                    # Create new metrics
                    metrics = MinerMetrics(
                        uid=miner_uid,
                        hotkey=hotkey,
                        miner_identity=miner_identity,
                        uid_assigned_at=datetime.utcnow(),
                        last_uid_verification=datetime.utcnow()
                    )
                    session.add(metrics)
                
                # Update uptime
                if is_online:
                    metrics.uptime_seconds += period_seconds
                metrics.total_uptime_periods += 1
                
                # Calculate uptime percentage (based on total periods)
                # Assuming each period is 5 minutes (300 seconds)
                total_time = metrics.total_uptime_periods * period_seconds
                if total_time > 0:
                    metrics.uptime_percentage = (metrics.uptime_seconds / total_time) * 100
                    metrics.uptime_score = min(1.0, metrics.uptime_percentage / 100.0)
                
                metrics.last_updated = datetime.utcnow()
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"❌ Error updating uptime: {e}")
                return False
            finally:
                session.close()
        except Exception as e:
            print(f"❌ Error in update_uptime: {e}")
            return False
    
    async def increment_invocation(self, miner_uid: int, hotkey: str):
        """Increment invocation count (successful user request)"""
        return await self.update_miner_metrics(
            miner_uid, hotkey,
            invocation_count=MinerMetrics.invocation_count + 1
        )
    
    async def update_diversity(self, miner_uid: int, hotkey: str, task_type: str, model_name: str = None):
        """Update diversity metrics (unique tasks/models)"""
        try:
            if not isinstance(self.db, PostgreSQLAdapter):
                return False
            
            session = self.db._get_session()
            try:
                miner_identity = f"{hotkey}_{miner_uid}"
                metrics = session.query(MinerMetrics).filter(
                    MinerMetrics.miner_identity == miner_identity
                ).first()
                
                if not metrics:
                    return False
                
                # Update diversity tasks
                diversity_tasks = metrics.diversity_tasks or []
                if task_type not in diversity_tasks:
                    diversity_tasks.append(task_type)
                    metrics.diversity_tasks = diversity_tasks
                    metrics.diversity_count = len(diversity_tasks)
                
                # Update diversity models
                if model_name:
                    diversity_models = metrics.diversity_models or []
                    if model_name not in diversity_models:
                        diversity_models.append(model_name)
                        metrics.diversity_models = diversity_models
                
                # Normalize diversity score (0-1)
                max_diversity = 10  # Assume max 10 different task types
                metrics.diversity_score = min(1.0, metrics.diversity_count / max_diversity)
                
                metrics.last_updated = datetime.utcnow()
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"❌ Error updating diversity: {e}")
                return False
            finally:
                session.close()
        except Exception as e:
            print(f"❌ Error in update_diversity: {e}")
            return False
    
    async def increment_bounty(self, miner_uid: int, hotkey: str):
        """Increment bounty count (priority/cold-start tasks)"""
        return await self.update_miner_metrics(
            miner_uid, hotkey,
            bounty_count=MinerMetrics.bounty_count + 1
        )
    
    async def update_response_time(self, miner_uid: int, hotkey: str, response_time: float):
        """Update average response time"""
        try:
            if not isinstance(self.db, PostgreSQLAdapter):
                return False
            
            session = self.db._get_session()
            try:
                miner_identity = f"{hotkey}_{miner_uid}"
                metrics = session.query(MinerMetrics).filter(
                    MinerMetrics.miner_identity == miner_identity
                ).first()
                
                if not metrics:
                    return False
                
                # Update running average
                metrics.response_count += 1
                metrics.total_response_time += response_time
                metrics.average_response_time = metrics.total_response_time / metrics.response_count
                
                metrics.last_updated = datetime.utcnow()
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                print(f"❌ Error updating response time: {e}")
                return False
            finally:
                session.close()
        except Exception as e:
            print(f"❌ Error in update_response_time: {e}")
            return False

