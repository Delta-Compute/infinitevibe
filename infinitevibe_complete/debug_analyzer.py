#!/usr/bin/env python3
import asyncio
import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient

async def test_analyzer():
    # Test the hardcoded miners
    top_miners_with_instagram = [
        {
            "hotkey": "5CAvipz4nDaf7d5YQyizWaFxJHCnK9qR4GFJqU1M4QLkKP4H",
            "engagement_rate": 2915291.67,
            "instagram_handle": "cristiano"
        },
        {
            "hotkey": "5EcJhyWkKuPRakXdMcU67sTHcHxyGfTD9eZ7UCtEvrB2pMQ7", 
            "engagement_rate": 2728766.67,
            "instagram_handle": "kyliejenner"
        },
        {
            "hotkey": "5DP2Zc4S",
            "engagement_rate": 1446621.43,
            "instagram_handle": "selenagomez"
        }
    ]
    
    print(f"🔍 Testing hardcoded miners list:")
    print(f"Total miners: {len(top_miners_with_instagram)}")
    
    for i, miner in enumerate(top_miners_with_instagram):
        print(f"  {i+1}. {miner['hotkey'][:8]}... (@{miner['instagram_handle']}) - {miner['engagement_rate']:,.2f}%")
    
    # Test MongoDB connection
    try:
        client = AsyncIOMotorClient('mongodb://localhost:27017/')
        db = client.infinitevibe
        collections = await db.list_collection_names()
        print(f"\n📊 MongoDB collections: {collections}")
        
        if collections:
            for collection_name in collections:
                count = await db[collection_name].count_documents({})
                print(f"  - {collection_name}: {count} documents")
        
    except Exception as e:
        print(f"❌ MongoDB error: {e}")
    
    # Test the logic that should return miners
    print(f"\n✅ Should return {len(top_miners_with_instagram[:5])} miners")
    return top_miners_with_instagram[:5]

asyncio.run(test_analyzer())
