#!/usr/bin/env python3
"""
Test script for the bot detection framework
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from detector import ModularBotDetector, FollowerData, DetectionResult
    from instagram_api import InstagramAPI
    
    print("✅ All imports successful")
    
    # Create a bot detector instance
    detector = ModularBotDetector()
    print(f"🤖 Bot detector created with {len(detector.analyzers)} analyzers")
    
    # Test with mock follower data
    mock_followers = [
        FollowerData(
            username="user123456",
            follower_count=50,
            following_count=5000,
            post_count=2,
            has_profile_pic=False,
            bio="",
            is_verified=False,
            is_private=False,
            account_creation_date=None
        ),
        FollowerData(
            username="real_user_john",
            follower_count=500,
            following_count=300,
            post_count=150,
            has_profile_pic=True,
            bio="Love photography and travel! 📸✈️",
            is_verified=False,
            is_private=False,
            account_creation_date=None
        )
    ]
    
    print(f"📊 Testing with {len(mock_followers)} mock followers...")
    
    # Run bot detection
    result = detector.analyze(mock_followers)
    
    print(f"🎯 Detection Results:")
    print(f"   Overall Authenticity Score: {result.overall_authenticity_score:.2f}")
    print(f"   Overall Confidence: {result.overall_confidence:.2f}")
    print(f"   Suspicious Followers: {result.suspicious_followers}")
    print(f"   Bot Probability: {result.bot_probability:.2f}")
    
    # Test Instagram API (mock mode)
    api = InstagramAPI()
    print("📱 Instagram API created successfully")
    
    # Test mock follower generation
    print("🧪 Testing mock follower generation...")
    mock_account = api._generate_mock_follower()
    print(f"   Generated mock follower: {mock_account.username}")
    
    print("\n✅ Bot detection framework is working correctly!")
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Make sure all dependencies are installed")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()