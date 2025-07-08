import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def debug_db():
    client = AsyncIOMotorClient('mongodb://localhost:27017/')
    db = client.infinitevibe
    
    print("🔍 Checking MongoDB collections...")
    collections = await db.list_collection_names()
    print(f"Collections: {collections}")
    print()
    
    # Check for engagement data in different possible collections
    for collection_name in collections:
        count = await db[collection_name].count_documents({})
        print(f"Collection '{collection_name}': {count} documents")
        
        # Sample a document to see the structure
        if count > 0:
            sample = await db[collection_name].find_one()
            print(f"Sample document from '{collection_name}':")
            print(f"  Keys: {list(sample.keys()) if sample else 'None'}")
            
            # Look for engagement-related fields
            if sample:
                sample_str = str(sample)
                if any(term in sample_str.lower() for term in ['engagement', 'hotkey', 'instagram', 'miner']):
                    print(f"  🎯 Found relevant data!")
                    if 'engagement_rate' in sample_str:
                        print(f"  ✅ Found engagement_rate field!")
                    if 'hotkey' in sample_str:
                        print(f"  ✅ Found hotkey field!")
                    if 'instagram' in sample_str:
                        print(f"  ✅ Found instagram field!")
            print()

asyncio.run(debug_db())
