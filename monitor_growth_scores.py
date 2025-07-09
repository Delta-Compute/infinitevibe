#!/usr/bin/env python3
"""
Monitor growth scores for active miners
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from tabulate import tabulate
import sys
sys.path.insert(0, 'src')

from new_growth_scoring import GrowthFocusedScoring

async def monitor_growth_scores():
    """Monitor and display growth scores for all miners"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017/")
    db = client.tensorflix
    
    performances = db["performances-0.0.2"]
    follower_history = db["follower_history"]
    follower_analysis = db["follower_analysis"]
    
    scorer = GrowthFocusedScoring()
    
    print("📊 Growth Score Monitor")
    print("=" * 80)
    
    # Get all miners with follower history
    miners = await follower_history.distinct("hotkey")
    
    score_data = []
    
    for hotkey in miners:
        # Get growth data  
        cutoff_date = datetime.utcnow() - timedelta(hours=12)
        
        historical = await follower_history.find_one(
            {"hotkey": hotkey, "timestamp": {"$gte": cutoff_date}},
            sort=[("timestamp", 1)]
        )
        
        current = await follower_history.find_one(
            {"hotkey": hotkey},
            sort=[("timestamp", -1)]
        )
        
        if not historical or not current:
            continue
            
        time_diff = current["timestamp"] - historical["timestamp"]
        hours_elapsed = time_diff.total_seconds() / 3600
        if hours_elapsed < 12:
            continue
        
        # Get engagement metrics
        perf_docs = await performances.find({"hotkey": hotkey}).to_list(None)
        total_likes = 0
        total_comments = 0
        
        for doc in perf_docs:
            platform_metrics = doc.get('platform_metrics_by_interval', {})
            for interval_key, metrics in platform_metrics.items():
                if 'instagram' in metrics.get('platform_name', '').lower():
                    total_likes += metrics.get('like_count', 0)
                    total_comments += metrics.get('comment_count', 0)
        
        # Get bot analysis
        bot_data = await follower_analysis.find_one({"hotkey": hotkey})
        bot_probability = 0.0
        bot_confidence = 0.0
        
        if bot_data:
            bot_probability = bot_data.get('bot_detection', {}).get('bot_probability', 0.0)
            bot_confidence = bot_data.get('bot_detection', {}).get('confidence', 0.0)
        
        # Calculate score
        result = await scorer.calculate_miner_score(
            hotkey=hotkey,
            current_followers=current["follower_count"],
            previous_followers=historical["follower_count"],
            hours_elapsed=hours_elapsed,
            likes=total_likes,
            comments=total_comments,
            bot_probability=bot_probability,
            bot_confidence=bot_confidence
        )
        
        if "reason" not in result:
            score_data.append({
                "Hotkey": hotkey[:8],
                "Followers": f"{current['follower_count']:,}",
                "Growth": f"{result['hourly_growth_rate']:.3f}%/hr",
                "Engagement": f"{result['engagement_multiplier']:.1f}x",
                "Bot Prob": f"{bot_probability:.1%}",
                "Score": f"{result['final_score']:.2f}"
            })
    
    # Sort by score
    score_data.sort(key=lambda x: float(x["Score"]), reverse=True)
    
    # Display top 20
    print("\n🏆 Top 20 Miners by Growth Score:")
    print(tabulate(score_data[:20], headers="keys", tablefmt="grid"))
    
    # Show scoring breakdown for top 5
    print("\n📈 Detailed Breakdown for Top 5:")
    for i, miner in enumerate(score_data[:5]):
        print(f"\n{i+1}. {miner['Hotkey']}:")
        print(f"   ├── Current Followers: {miner['Followers']}")
        print(f"   ├── Hourly Growth Rate: {miner['Growth']}")
        print(f"   ├── Engagement Multiplier: {miner['Engagement']}")
        print(f"   ├── Bot Probability: {miner['Bot Prob']}")
        print(f"   └── Final Score: {miner['Score']}")

if __name__ == "__main__":
    asyncio.run(monitor_growth_scores())