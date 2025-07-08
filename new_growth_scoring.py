#!/usr/bin/env python3
"""
New growth-focused scoring system for InfiniteVibe validator
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Optional

class GrowthFocusedScoring:
    """
    New scoring system that prioritizes authentic follower growth
    """
    
    def __init__(self):
        # Scoring weights
        self.growth_weight = 0.7      # 70% of score from growth
        self.engagement_weight = 0.3   # 30% of score from engagement
        
        # Growth parameters
        self.min_followers_threshold = 500       # Lower threshold for faster testing
        self.min_analysis_period_hours = 12      # Need 12 hours of data
        self.max_hourly_growth_rate = 0.01       # Cap at 1% hourly growth (anti-spike)
        
        # Bot penalty parameters
        self.bot_threshold = 0.6                 # More strict than before
        self.max_bot_penalty = 0.9               # 90% penalty for bots
        
    async def calculate_miner_score(
        self, 
        hotkey: str,
        current_followers: int,
        previous_followers: int,
        hours_elapsed: float,
        likes: int,
        comments: int,
        bot_probability: float,
        bot_confidence: float
    ) -> Dict[str, float]:
        """
        Calculate new growth-focused score for a miner
        
        Returns:
            Dict with score breakdown
        """
        
        # 1. MINIMUM REQUIREMENTS CHECK
        if current_followers < self.min_followers_threshold:
            return {
                "final_score": 0.0,
                "reason": f"Below minimum {self.min_followers_threshold} followers",
                "growth_score": 0.0,
                "engagement_multiplier": 0.0,
                "bot_penalty": 1.0
            }
        
        if hours_elapsed < self.min_analysis_period_hours:
            return {
                "final_score": 0.0,
                "reason": f"Need {self.min_analysis_period_hours} hours of data",
                "growth_score": 0.0,
                "engagement_multiplier": 0.0,
                "bot_penalty": 1.0
            }
        
        # 2. FOLLOWER GROWTH CALCULATION
        follower_change = current_followers - previous_followers
        hourly_growth_rate = follower_change / previous_followers / hours_elapsed
        
        # Cap extreme growth (likely bot purchases)
        capped_growth_rate = min(hourly_growth_rate, self.max_hourly_growth_rate)
        
        # Convert to percentage and apply logarithmic scaling
        growth_percentage = capped_growth_rate * 100
        
        # Growth score: reward positive growth, heavily penalize negative
        if growth_percentage > 0:
            growth_score = math.log10(1 + growth_percentage) * 100  # Log scale for diminishing returns
        else:
            growth_score = growth_percentage * 5  # 5x penalty for losing followers
            
        # 3. BOT AUTHENTICITY MULTIPLIER
        if bot_probability > self.bot_threshold and bot_confidence > 0.5:
            # Heavy penalties for bot followers
            authenticity_multiplier = max(
                1.0 - self.max_bot_penalty, 
                1.0 - (bot_probability * self.max_bot_penalty)
            )
        else:
            authenticity_multiplier = 1.0
            
        # Apply authenticity to growth score
        authentic_growth_score = growth_score * authenticity_multiplier * self.growth_weight
        
        # 4. ENGAGEMENT MULTIPLIER (Must have BOTH growth AND engagement)
        if current_followers > 0:
            engagement_rate = ((likes + comments) / current_followers) * 100
            # Cap engagement rate to prevent bot gaming
            capped_engagement = min(engagement_rate, 8.0)  # Max 8% engagement rate
            
            # Engagement multiplier: 0.5x to 2.0x based on engagement
            # No engagement = 50% penalty, good engagement = 2x bonus
            min_multiplier = 0.5
            max_multiplier = 2.0
            engagement_multiplier = min_multiplier + (capped_engagement / 8.0) * (max_multiplier - min_multiplier)
        else:
            engagement_multiplier = 0.0  # No followers = no score
            
        # 5. FINAL SCORE: MULTIPLICATIVE (need BOTH growth AND engagement)
        if authentic_growth_score <= 0:
            final_score = 0.0  # No growth = no rewards regardless of engagement
        else:
            final_score = authentic_growth_score * engagement_multiplier
        
        return {
            "final_score": final_score,
            "growth_score": authentic_growth_score,
            "engagement_multiplier": engagement_multiplier,
            "bot_penalty": authenticity_multiplier,
            "hourly_growth_rate": hourly_growth_rate * 100,  # As percentage
            "raw_growth_score": growth_score,
            "capped_growth_rate": capped_growth_rate * 100
        }
    
    def get_score_breakdown_explanation(self, score_data: Dict) -> str:
        """Generate human-readable explanation of score"""
        return f"""
Score Breakdown:
├── Growth Score: {score_data['growth_score']:.2f} (70% weight)
│   ├── Hourly Growth Rate: {score_data['hourly_growth_rate']:.3f}%
│   ├── Raw Growth Score: {score_data['raw_growth_score']:.2f}
│   └── Bot Penalty Applied: {score_data['bot_penalty']:.2f}x
├── Engagement Multiplier: {score_data['engagement_multiplier']:.2f}x (0.5x to 2.0x)
└── Final Score: {score_data['final_score']:.2f}
        """

# Example usage and test scenarios
async def test_scoring_scenarios():
    """Test the new scoring system with various scenarios"""
    
    scorer = GrowthFocusedScoring()
    
    scenarios = [
        {
            "name": "Healthy Organic Growth",
            "current_followers": 5000,
            "previous_followers": 4000,
            "hours_elapsed": 24,
            "likes": 200,
            "comments": 50,
            "bot_probability": 0.2,
            "bot_confidence": 0.8
        },
        {
            "name": "Bot Follower Purchase",
            "current_followers": 10000,
            "previous_followers": 2000,
            "hours_elapsed": 12,
            "likes": 100,
            "comments": 10,
            "bot_probability": 0.9,
            "bot_confidence": 0.9
        },
        {
            "name": "High Engagement, Slow Growth",
            "current_followers": 3000,
            "previous_followers": 2800,
            "hours_elapsed": 18,
            "likes": 300,
            "comments": 100,
            "bot_probability": 0.1,
            "bot_confidence": 0.7
        },
        {
            "name": "Losing Followers (Authentic)",
            "current_followers": 4500,
            "previous_followers": 5000,
            "hours_elapsed": 36,
            "likes": 180,
            "comments": 40,
            "bot_probability": 0.3,
            "bot_confidence": 0.6
        },
        {
            "name": "New Account (Below Threshold)",
            "current_followers": 500,
            "previous_followers": 100,
            "hours_elapsed": 15,
            "likes": 50,
            "comments": 20,
            "bot_probability": 0.1,
            "bot_confidence": 0.5
        },
        {
            "name": "Zero Growth + Massive Bot Engagement",
            "current_followers": 2000,
            "previous_followers": 2000,  # NO GROWTH
            "hours_elapsed": 18,
            "likes": 5000,  # Huge botted likes
            "comments": 1000,  # Huge botted comments  
            "bot_probability": 0.1,  # Somehow not detected as bots
            "bot_confidence": 0.3
        },
        {
            "name": "Growth + Zero Engagement",
            "current_followers": 3000,
            "previous_followers": 2000,  # Good growth
            "hours_elapsed": 24,
            "likes": 0,  # No engagement at all
            "comments": 0,
            "bot_probability": 0.2,
            "bot_confidence": 0.8
        }
    ]
    
    print("🚀 New Growth-Focused Scoring System Test Results")
    print("=" * 60)
    
    for scenario in scenarios:
        print(f"\n📊 Scenario: {scenario['name']}")
        print("-" * 40)
        
        score_data = await scorer.calculate_miner_score(
            hotkey="test_hotkey",
            **{k: v for k, v in scenario.items() if k != "name"}
        )
        
        if "reason" in score_data:
            print(f"❌ Disqualified: {score_data['reason']}")
        else:
            print(scorer.get_score_breakdown_explanation(score_data))

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_scoring_scenarios())