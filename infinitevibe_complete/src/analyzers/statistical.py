"""
Statistical analyzer for detecting bot followers through patterns.
"""

import math
import statistics
from collections import Counter
from typing import List, Dict, Any
from .base import BaseAnalyzer, FollowerData, AnalyzerResult


class StatisticalAnalyzer(BaseAnalyzer):
    """Analyze followers using statistical patterns"""
    
    def __init__(self):
        super().__init__("Statistical Pattern Analyzer", "1.0.0")
        
    def get_required_fields(self) -> List[str]:
        return ["username", "follower_count", "following_count", "posts_count", "bio", "location"]
    
    def analyze(self, followers_data: List[FollowerData]) -> AnalyzerResult:
        """Analyze statistical patterns in follower data"""
        if not self.can_analyze(followers_data):
            return AnalyzerResult(
                analyzer_name=self.name,
                authenticity_score=0.5,
                confidence=0.0,
                details={"error": "Insufficient data for analysis"},
                flags=["insufficient_data"]
            )
        
        # Calculate individual metrics
        username_entropy = self._calculate_username_entropy(followers_data)
        ratio_analysis = self._analyze_follower_ratios(followers_data)
        bio_completeness = self._analyze_bio_completeness(followers_data)
        location_clustering = self._analyze_location_clustering(followers_data)
        posts_distribution = self._analyze_posts_distribution(followers_data)
        
        # Combine metrics with weights
        weighted_score = (
            username_entropy * 0.25 +
            ratio_analysis['score'] * 0.25 +
            bio_completeness * 0.20 +
            location_clustering * 0.15 +
            posts_distribution * 0.15
        )
        
        # Collect flags from all analyses
        flags = []
        if username_entropy < 0.3:
            flags.append("low_username_entropy")
        if ratio_analysis['bot_ratio'] > 0.7:
            flags.append("suspicious_follower_ratios")
        if bio_completeness < 0.2:
            flags.append("low_bio_completion")
        if location_clustering < 0.3:
            flags.append("geographic_clustering")
        if posts_distribution < 0.3:
            flags.append("unusual_posting_patterns")
        
        # Calculate confidence based on sample size and data quality
        confidence = min(1.0, len(followers_data) / 100) * 0.8
        
        return AnalyzerResult(
            analyzer_name=self.name,
            authenticity_score=weighted_score,
            confidence=confidence,
            details={
                "username_entropy": username_entropy,
                "ratio_analysis": ratio_analysis,
                "bio_completeness": bio_completeness,
                "location_clustering": location_clustering,
                "posts_distribution": posts_distribution,
                "sample_size": len(followers_data)
            },
            flags=flags
        )
    
    def _calculate_username_entropy(self, followers_data: List[FollowerData]) -> float:
        """Calculate average entropy of usernames (higher = more random/bot-like)"""
        if not followers_data:
            return 0.0
        
        entropies = []
        for follower in followers_data:
            username = follower.username.lower()
            if len(username) == 0:
                continue
                
            # Calculate character frequency
            char_counts = Counter(username)
            total_chars = len(username)
            
            # Calculate entropy
            entropy = 0.0
            for count in char_counts.values():
                probability = count / total_chars
                if probability > 0:
                    entropy -= probability * math.log2(probability)
            
            entropies.append(entropy)
        
        if not entropies:
            return 0.0
            
        avg_entropy = statistics.mean(entropies)
        # Normalize to 0-1 scale (typical usernames have entropy 2-4)
        normalized = min(1.0, avg_entropy / 4.0)
        
        # Invert so higher score = more human-like
        return 1.0 - normalized
    
    def _analyze_follower_ratios(self, followers_data: List[FollowerData]) -> Dict[str, Any]:
        """Analyze follower-to-following ratios"""
        ratios = []
        suspicious_count = 0
        
        for follower in followers_data:
            ratio = follower.follower_following_ratio
            if ratio == float('inf'):
                ratio = 1000  # Cap infinite ratios
            ratios.append(ratio)
            
            # Flag suspicious patterns
            if (follower.following_count > 1000 and 
                follower.follower_count < 100):
                suspicious_count += 1
            elif (follower.following_count == 0 and 
                  follower.follower_count == 0):
                suspicious_count += 1
        
        if not ratios:
            return {"score": 0.0, "bot_ratio": 1.0, "avg_ratio": 0.0}
        
        avg_ratio = statistics.mean(ratios)
        bot_ratio = suspicious_count / len(followers_data)
        
        # Score based on how normal the distribution looks
        score = 1.0 - bot_ratio
        
        return {
            "score": score,
            "bot_ratio": bot_ratio,
            "avg_ratio": avg_ratio,
            "suspicious_count": suspicious_count
        }
    
    def _analyze_bio_completeness(self, followers_data: List[FollowerData]) -> float:
        """Analyze bio completion rates"""
        if not followers_data:
            return 0.0
        
        completed_bios = sum(1 for f in followers_data if f.bio and len(f.bio.strip()) > 0)
        completion_rate = completed_bios / len(followers_data)
        
        # Human accounts typically have 60-80% bio completion
        # Bots often have 0-20% completion
        if completion_rate > 0.6:
            return 1.0
        elif completion_rate > 0.4:
            return 0.8
        elif completion_rate > 0.2:
            return 0.4
        else:
            return 0.0
    
    def _analyze_location_clustering(self, followers_data: List[FollowerData]) -> float:
        """Analyze geographic distribution of followers"""
        locations = [f.location for f in followers_data if f.location]
        
        if len(locations) < 5:
            return 0.5  # Not enough data
        
        # Count location frequency
        location_counts = Counter(locations)
        total_with_location = len(locations)
        
        # Calculate distribution score
        unique_locations = len(location_counts)
        if unique_locations == 0:
            return 0.0
        
        # Check for excessive clustering
        max_concentration = max(location_counts.values()) / total_with_location
        
        if max_concentration > 0.8:  # 80% from same location
            return 0.1
        elif max_concentration > 0.6:  # 60% from same location
            return 0.3
        elif max_concentration > 0.4:  # 40% from same location
            return 0.6
        else:
            return 1.0
    
    def _analyze_posts_distribution(self, followers_data: List[FollowerData]) -> float:
        """Analyze distribution of post counts"""
        post_counts = [f.posts_count for f in followers_data]
        
        if not post_counts:
            return 0.0
        
        # Count accounts with 0 posts (red flag)
        zero_posts = sum(1 for count in post_counts if count == 0)
        zero_ratio = zero_posts / len(post_counts)
        
        if zero_ratio > 0.8:  # 80% have no posts
            return 0.1
        elif zero_ratio > 0.6:  # 60% have no posts
            return 0.3
        elif zero_ratio > 0.4:  # 40% have no posts
            return 0.6
        else:
            return 1.0