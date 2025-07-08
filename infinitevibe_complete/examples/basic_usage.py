"""
Basic usage example for the follower analysis framework.
"""

import sys
import os
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from analyzers.base import FollowerData
from detector import ModularBotDetector


def create_sample_data():
    """Create sample follower data for demonstration"""
    
    # Human-like followers
    human_followers = [
        FollowerData(
            username="john_photographer",
            follower_count=1200,
            following_count=450,
            posts_count=89,
            bio="Professional photographer | Nature lover 📸🌲",
            profile_picture_url="https://example.com/john.jpg",
            is_verified=False,
            is_business=True,
            is_private=False,
            account_creation_date=datetime.now() - timedelta(days=720),
            last_post_date=datetime.now() - timedelta(days=3),
            location="Seattle, WA",
            external_url="https://johnphoto.com"
        ),
        FollowerData(
            username="maria_travels",
            follower_count=850,
            following_count=380,
            posts_count=156,
            bio="Travel blogger ✈️ | Coffee enthusiast ☕",
            profile_picture_url="https://example.com/maria.jpg",
            is_verified=False,
            is_business=False,
            is_private=False,
            account_creation_date=datetime.now() - timedelta(days=1095),
            last_post_date=datetime.now() - timedelta(days=1),
            location="Barcelona, Spain",
            external_url="https://mariatravels.blog"
        )
    ]
    
    # Bot-like followers
    bot_followers = [
        FollowerData(
            username="user_1234567890",
            follower_count=8,
            following_count=2500,
            posts_count=0,
            bio="",
            profile_picture_url=None,
            is_verified=False,
            is_business=False,
            is_private=False,
            account_creation_date=datetime.now() - timedelta(days=5),
            last_post_date=None,
            location=None,
            external_url=None
        ),
        FollowerData(
            username="bot_account_456",
            follower_count=15,
            following_count=1800,
            posts_count=2,
            bio="",
            profile_picture_url=None,
            is_verified=False,
            is_business=False,
            is_private=False,
            account_creation_date=datetime.now() - timedelta(days=12),
            last_post_date=datetime.now() - timedelta(days=400),
            location=None,
            external_url=None
        )
    ]
    
    return human_followers, bot_followers


def main():
    """Demonstrate basic usage of the follower analysis framework"""
    
    print("🤖 InfiniteVibe Follower Analysis Framework")
    print("=" * 50)
    
    # Create detector
    detector = ModularBotDetector()
    
    # Show analyzer information
    print("\n📊 Registered Analyzers:")
    analyzer_info = detector.get_analyzer_info()
    for name, info in analyzer_info.items():
        print(f"  • {info['name']} v{info['version']} (weight: {info['weight']:.2f})")
    
    # Create sample data
    human_followers, bot_followers = create_sample_data()
    
    # Analyze human-like followers
    print("\n🧑‍🤝‍🧑 Analyzing Human-like Followers:")
    print("-" * 40)
    human_result = detector.analyze(human_followers)
    print(f"Authenticity Score: {human_result.overall_authenticity_score:.3f}")
    print(f"Bot Probability: {human_result.bot_probability:.3f}")
    print(f"Risk Level: {human_result.risk_level}")
    print(f"Confidence: {human_result.overall_confidence:.3f}")
    if human_result.flags:
        print(f"Flags: {', '.join(human_result.flags)}")
    
    # Show individual analyzer results
    print("\n  Individual Analyzer Results:")
    for result in human_result.analyzer_results:
        print(f"  • {result.analyzer_name}: {result.authenticity_score:.3f} (confidence: {result.confidence:.3f})")
    
    # Analyze bot-like followers
    print("\n🤖 Analyzing Bot-like Followers:")
    print("-" * 40)
    bot_result = detector.analyze(bot_followers)
    print(f"Authenticity Score: {bot_result.overall_authenticity_score:.3f}")
    print(f"Bot Probability: {bot_result.bot_probability:.3f}")
    print(f"Risk Level: {bot_result.risk_level}")
    print(f"Confidence: {bot_result.overall_confidence:.3f}")
    if bot_result.flags:
        print(f"Flags: {', '.join(bot_result.flags)}")
    
    # Show individual analyzer results
    print("\n  Individual Analyzer Results:")
    for result in bot_result.analyzer_results:
        print(f"  • {result.analyzer_name}: {result.authenticity_score:.3f} (confidence: {result.confidence:.3f})")
    
    # Mixed analysis
    print("\n🔄 Analyzing Mixed Followers:")
    print("-" * 40)
    mixed_followers = human_followers + bot_followers
    mixed_result = detector.analyze(mixed_followers)
    print(f"Authenticity Score: {mixed_result.overall_authenticity_score:.3f}")
    print(f"Bot Probability: {mixed_result.bot_probability:.3f}")
    print(f"Risk Level: {mixed_result.risk_level}")
    print(f"Confidence: {mixed_result.overall_confidence:.3f}")
    
    # Demonstrate single account analysis
    print("\n👤 Single Account Analysis:")
    print("-" * 40)
    single_result = detector.analyze_single_account(bot_followers[0])
    print(f"Account: {bot_followers[0].username}")
    print(f"Bot Probability: {single_result.bot_probability:.3f}")
    print(f"Risk Level: {single_result.risk_level}")
    
    # Show JSON export
    print("\n📄 JSON Export Sample:")
    print("-" * 40)
    json_output = human_result.to_json()
    # Show first 200 characters
    print(json_output[:200] + "..." if len(json_output) > 200 else json_output)
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()