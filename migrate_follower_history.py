#!/usr/bin/env python3
"""
Migration script to populate initial follower history from existing performance data
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import sys

async def migrate_follower_history():
    """Migrate existing follower counts to history collection"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017/")
    db = client.tensorflix
    
    performances = db["performances-0.0.2"]
    follower_history = db["follower_history"]
    
    print("🔄 Starting follower history migration...")
    
    # Get all unique hotkeys
    hotkeys = await performances.distinct("hotkey")
    print(f"Found {len(hotkeys)} unique miners")
    
    migrated = 0
    for hotkey in hotkeys:
        # Get all performance documents for this hotkey
        perf_docs = await performances.find({"hotkey": hotkey}).to_list(None)
        
        follower_count = 0
        for doc in perf_docs:
            platform_metrics = doc.get('platform_metrics_by_interval', {})
            
            for interval_key, metrics in platform_metrics.items():
                # Only process Instagram content
                if 'instagram' in metrics.get('platform_name', '').lower():
                    if metrics.get('owner_follower_count', 0) > 0:
                        follower_count = metrics['owner_follower_count']
                        
                        # Parse interval timestamp
                        try:
                            timestamp = datetime.strptime(interval_key, "%Y-%m-%d-%H-%M")
                        except:
                            timestamp = datetime.utcnow()
                        
                        # Create history record
                        history_record = {
                            "hotkey": hotkey,
                            "timestamp": timestamp,
                            "follower_count": follower_count,
                            "bot_analysis": {}  # Will be populated by bot detector
                        }
                        
                        # Insert if not exists
                        existing = await follower_history.find_one({
                            "hotkey": hotkey,
                            "timestamp": timestamp
                        })
                        
                        if not existing:
                            await follower_history.insert_one(history_record)
                            migrated += 1
        
        if follower_count > 0:
            print(f"✅ Migrated {hotkey[:8]}: {follower_count} followers")
    
    # Create indexes
    await follower_history.create_index([("hotkey", 1), ("timestamp", -1)])
    await follower_history.create_index("timestamp")
    
    print(f"\n✅ Migration complete! Migrated {migrated} follower history records")
    
    # Show sample data
    sample = await follower_history.find().limit(5).to_list(None)
    print("\n📊 Sample migrated data:")
    for record in sample:
        print(f"  - {record['hotkey'][:8]}: {record['follower_count']} followers at {record['timestamp']}")

if __name__ == "__main__":
    asyncio.run(migrate_follower_history())