"""
Temporal pattern analyzer for detecting bot followers through time-based patterns.
"""

import statistics
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from .base import BaseAnalyzer, FollowerData, AnalyzerResult


class TemporalAnalyzer(BaseAnalyzer):
    """Analyze followers using time-based patterns"""
    
    def __init__(self):
        super().__init__("Temporal Pattern Analyzer", "1.0.0")
        
    def get_required_fields(self) -> List[str]:
        return ["username", "account_creation_date", "last_post_date"]
    
    def analyze(self, followers_data: List[FollowerData]) -> AnalyzerResult:
        """Analyze temporal patterns in follower data"""
        if not self.can_analyze(followers_data):
            return AnalyzerResult(
                analyzer_name=self.name,
                authenticity_score=0.5,
                confidence=0.0,
                details={"error": "Insufficient temporal data for analysis"},
                flags=["insufficient_temporal_data"]
            )
        
        # Filter data with valid timestamps
        valid_followers = [
            f for f in followers_data 
            if f.account_creation_date is not None
        ]
        
        if len(valid_followers) < 10:
            return AnalyzerResult(
                analyzer_name=self.name,
                authenticity_score=0.5,
                confidence=0.1,
                details={"error": "Not enough temporal data"},
                flags=["insufficient_temporal_data"]
            )
        
        # Calculate individual metrics
        creation_clustering = self._analyze_creation_clustering(valid_followers)
        account_age_distribution = self._analyze_account_age_distribution(valid_followers)
        activity_patterns = self._analyze_activity_patterns(valid_followers)
        
        # Combine metrics with weights
        weighted_score = (
            creation_clustering * 0.4 +
            account_age_distribution * 0.3 +
            activity_patterns * 0.3
        )
        
        # Collect flags
        flags = []
        if creation_clustering < 0.3:
            flags.append("bulk_account_creation")
        if account_age_distribution < 0.3:
            flags.append("suspicious_account_ages")
        if activity_patterns < 0.3:
            flags.append("irregular_activity_patterns")
        
        # Calculate confidence
        confidence = min(1.0, len(valid_followers) / 50) * 0.9
        
        return AnalyzerResult(
            analyzer_name=self.name,
            authenticity_score=weighted_score,
            confidence=confidence,
            details={
                "creation_clustering": creation_clustering,
                "account_age_distribution": account_age_distribution,
                "activity_patterns": activity_patterns,
                "valid_sample_size": len(valid_followers)
            },
            flags=flags
        )
    
    def _analyze_creation_clustering(self, followers_data: List[FollowerData]) -> float:
        """Detect bulk account creation patterns"""
        if not followers_data:
            return 0.0
        
        # Group creation dates by day
        creation_days = defaultdict(int)
        for follower in followers_data:
            if follower.account_creation_date:
                day_key = follower.account_creation_date.strftime("%Y-%m-%d")
                creation_days[day_key] += 1
        
        if not creation_days:
            return 0.0
        
        total_accounts = len(followers_data)
        daily_counts = list(creation_days.values())
        
        # Calculate clustering score
        max_single_day = max(daily_counts)
        max_day_ratio = max_single_day / total_accounts
        
        # Check for suspicious clustering
        if max_day_ratio > 0.5:  # 50% created on same day
            return 0.1
        elif max_day_ratio > 0.3:  # 30% created on same day
            return 0.3
        elif max_day_ratio > 0.15:  # 15% created on same day
            return 0.6
        else:
            return 1.0
    
    def _analyze_account_age_distribution(self, followers_data: List[FollowerData]) -> float:
        """Analyze distribution of account ages"""
        if not followers_data:
            return 0.0
        
        now = datetime.now()
        ages_in_days = []
        
        for follower in followers_data:
            if follower.account_creation_date:
                age = (now - follower.account_creation_date).days
                ages_in_days.append(age)
        
        if not ages_in_days:
            return 0.0
        
        # Calculate age statistics
        avg_age = statistics.mean(ages_in_days)
        
        # Count very new accounts (< 30 days)
        very_new = sum(1 for age in ages_in_days if age < 30)
        new_ratio = very_new / len(ages_in_days)
        
        # Count accounts created in suspicious timeframes
        recent_count = sum(1 for age in ages_in_days if age < 90)
        recent_ratio = recent_count / len(ages_in_days)
        
        # Scoring based on age distribution
        if new_ratio > 0.8:  # 80% very new accounts
            return 0.1
        elif new_ratio > 0.6:  # 60% very new accounts
            return 0.3
        elif recent_ratio > 0.8:  # 80% recent accounts
            return 0.4
        elif avg_age < 90:  # Average age < 3 months
            return 0.5
        else:
            return 1.0
    
    def _analyze_activity_patterns(self, followers_data: List[FollowerData]) -> float:
        """Analyze posting activity patterns"""
        if not followers_data:
            return 0.0
        
        now = datetime.now()
        active_accounts = 0
        inactive_accounts = 0
        activity_scores = []
        
        for follower in followers_data:
            if not follower.last_post_date:
                inactive_accounts += 1
                continue
            
            # Calculate days since last post
            days_since_post = (now - follower.last_post_date).days
            
            if days_since_post <= 30:  # Posted within last month
                active_accounts += 1
                activity_scores.append(1.0)
            elif days_since_post <= 90:  # Posted within last 3 months
                activity_scores.append(0.7)
            elif days_since_post <= 180:  # Posted within last 6 months
                activity_scores.append(0.4)
            else:
                activity_scores.append(0.1)
        
        total_accounts = len(followers_data)
        inactive_ratio = inactive_accounts / total_accounts
        
        # Heavy penalty for high inactive ratio
        if inactive_ratio > 0.8:  # 80% never posted
            return 0.1
        elif inactive_ratio > 0.6:  # 60% never posted
            return 0.2
        elif inactive_ratio > 0.4:  # 40% never posted
            return 0.5
        
        # Calculate average activity score
        if activity_scores:
            avg_activity = statistics.mean(activity_scores)
            return avg_activity
        else:
            return 0.1  # All inactive
    
    def _detect_coordinated_timing(self, followers_data: List[FollowerData]) -> Dict[str, Any]:
        """Detect coordinated timing patterns (advanced analysis)"""
        if not followers_data:
            return {"score": 0.0, "coordinated_groups": 0}
        
        # Group by creation time windows (1-hour buckets)
        time_buckets = defaultdict(list)
        
        for follower in followers_data:
            if follower.account_creation_date:
                # Create 1-hour bucket key
                bucket_time = follower.account_creation_date.replace(minute=0, second=0, microsecond=0)
                time_buckets[bucket_time].append(follower.username)
        
        # Find suspicious clusters
        coordinated_groups = 0
        for bucket_time, usernames in time_buckets.items():
            if len(usernames) >= 5:  # 5+ accounts in same hour
                coordinated_groups += 1
        
        # Calculate score
        total_buckets = len(time_buckets)
        if total_buckets == 0:
            return {"score": 0.0, "coordinated_groups": 0}
        
        coordination_ratio = coordinated_groups / total_buckets
        score = 1.0 - min(1.0, coordination_ratio * 2)  # Penalty for coordination
        
        return {
            "score": score,
            "coordinated_groups": coordinated_groups,
            "total_buckets": total_buckets
        }