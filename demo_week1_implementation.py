#!/usr/bin/env python3
"""
Demonstration of Week 1 implementation without requiring MongoDB.
Shows the data models, parsing, and scoring logic.
"""

from datetime import datetime, timedelta
from tensorflix.models.brief import (
    Brief, BriefSubmission, BriefStatus, 
    SubmissionType, ValidationStatus, BriefCommitMessage
)
from tensorflix.utils.ids import generate_brief_id, generate_submission_id


def demo_brief_models():
    """Demonstrate brief and submission models."""
    print("=== Brief Data Models ===\n")
    
    # Create a brief
    brief_id = generate_brief_id()
    brief = Brief(
        brief_id=brief_id,
        user_email="creator@infinitevibe.ai",
        title="Create a 30-second AI video about future tech",
        description="Looking for creative AI-generated video showcasing future technology concepts. Should include futuristic visuals, smooth transitions, and engaging narrative.",
        requirements="MP4 format, 1080p resolution, 30 seconds duration, AI-generated only"
    )
    
    print(f"✅ Brief Created:")
    print(f"   ID: {brief.brief_id}")
    print(f"   Title: {brief.title}")
    print(f"   Created: {brief.created_at}")
    print(f"   6hr deadline: {brief.deadline_6hr}")
    print(f"   24hr deadline: {brief.deadline_24hr}")
    print(f"   Status: {brief.status}")
    print(f"   Is Active: {brief.is_active()}")
    
    # Create submissions
    print("\n✅ Sample Submissions:")
    
    miners = [
        "5Eg2TvA5G4f7K9Kj6Vn89Lm3Qw2Rs1Tx9Yz8",
        "5Fg3QwB6H5g8L2Pn4Km7Vx9Rt1Qs3Wy5Ez2",
        "5Hg4RxC7I6h9M3Qo5Ln8Wy0Su2Pt4Xz6Fa3"
    ]
    
    submissions = []
    for i, miner in enumerate(miners):
        # Simulate different submission times
        submit_time = brief.created_at + timedelta(hours=i*2)
        
        sub = BriefSubmission(
            submission_id=generate_submission_id(brief_id, miner, "sub_1"),
            brief_id=brief_id,
            miner_hotkey=miner,
            submission_type=SubmissionType.SUB_1,
            r2_link=f"https://infinitevibe.r2.dev/submissions/{brief_id}/video_{i}.mp4",
            submitted_at=submit_time,
            validation_status=ValidationStatus.VALID
        )
        submissions.append(sub)
        
        speed_score = sub.calculate_speed_score(brief)
        print(f"\n   Miner {i+1}: {miner[-8:]}")
        print(f"   Submitted after: {(submit_time - brief.created_at).total_seconds()/3600:.1f} hours")
        print(f"   Speed Score: {speed_score:.2f}/30 points")
    
    # Simulate top 10 selection
    brief.top_10_miners = [miners[0], miners[1]]
    brief.status = BriefStatus.SELECTING_TOP10
    
    print("\n✅ After Top 10 Selection:")
    for sub in submissions[:2]:
        selection_score = sub.calculate_selection_score(brief)
        print(f"   {sub.miner_hotkey[-8:]}: {selection_score:.0f} selection points")
    
    # Simulate final selection
    brief.final_3_miners = [miners[0]]
    brief.status = BriefStatus.COMPLETED
    
    print("\n✅ Final Scoring:")
    for sub in submissions:
        total_score = sub.calculate_total_score(brief)
        speed = sub.calculate_speed_score(brief)
        selection = sub.calculate_selection_score(brief)
        print(f"   {sub.miner_hotkey[-8:]}: {total_score:.2f} total ({speed:.2f} speed + {selection:.0f} selection)")


def demo_commit_parsing():
    """Demonstrate brief commit message parsing."""
    print("\n\n=== Brief Commit Message Parsing ===\n")
    
    # Test various commit formats
    test_commits = [
        # Valid brief submissions
        ("brief_20241204_abc123:sub_1:https://r2.storage/video1.mp4", True),
        ("brief_20241204_xyz789:sub_2:https://r2.storage/revision.mp4", True),
        
        # Traditional gist format (should not parse as brief)
        ("toilaluan:1234567890abcdef", False),
        ("john:gist123456", False),
        
        # Invalid formats
        ("brief123:invalid_sub:https://r2.storage/video.mp4", False),
        ("", False),
        ("malformed", False),
    ]
    
    for commit_msg, expected_valid in test_commits:
        parsed = BriefCommitMessage.parse(commit_msg)
        is_valid = parsed is not None
        status = "✅" if is_valid == expected_valid else "❌"
        
        print(f"{status} '{commit_msg}'")
        if parsed:
            print(f"   → Brief ID: {parsed.brief_id}")
            print(f"   → Type: {parsed.submission_type.value}")
            print(f"   → R2 Link: {parsed.r2_link}")
        else:
            print(f"   → Not a brief submission (traditional format or invalid)")
        print()


def demo_r2_storage_paths():
    """Demonstrate R2 storage path structure."""
    print("\n=== R2 Storage Structure ===\n")
    
    brief_id = "brief_20241204_abc123"
    miner_hotkey = "5Eg2TvA5G4f7K9Kj6Vn89Lm3Qw2Rs1Tx9Yz8"
    
    print("✅ R2 Path Convention:")
    print(f"   /submissions/{brief_id}/{miner_hotkey[-8:]}_sub_1.mp4")
    print(f"   /submissions/{brief_id}/{miner_hotkey[-8:]}_sub_2.mp4")
    
    print("\n✅ Example URLs:")
    print(f"   https://infinitevibe.r2.dev/submissions/{brief_id}/{miner_hotkey[-8:]}_sub_1.mp4")
    print(f"   https://custom-domain.com/submissions/{brief_id}/{miner_hotkey[-8:]}_sub_2.mp4")


def demo_scoring_algorithm():
    """Demonstrate the new scoring algorithm."""
    print("\n\n=== Brief-Based Scoring Algorithm ===\n")
    
    print("✅ Scoring Components:")
    print("   1. Speed Score (0-30 points)")
    print("      - First hour: 30 points")
    print("      - Linear decay to 0 at 24 hours")
    print()
    print("   2. Selection Score (0-70 points)")
    print("      - Selected in top 10: +30 points")
    print("      - Selected in final 3: +40 points")
    print()
    print("   3. Quality Multiplier (0-1)")
    print("      - Based on AI detection and validation")
    print()
    
    # Show example scoring timeline
    print("✅ Speed Score Timeline:")
    hours = [0.5, 1, 2, 4, 8, 12, 16, 20, 24]
    for h in hours:
        if h <= 1:
            score = 30.0
        elif h >= 24:
            score = 0.0
        else:
            score = 30.0 * (1 - (h - 1) / 23)
        print(f"   {h:4.1f} hours: {score:5.2f} points")


def main():
    """Run all demonstrations."""
    print("InfiniteVibe Week 1 Implementation Demo")
    print("=" * 50)
    print("\nThis demo shows the implemented functionality without")
    print("requiring MongoDB or external services to be running.\n")
    
    # Run demos
    demo_brief_models()
    demo_commit_parsing()
    demo_r2_storage_paths()
    demo_scoring_algorithm()
    
    print("\n" + "=" * 50)
    print("✅ Week 1 Implementation Complete!\n")
    print("Key Features Implemented:")
    print("1. ✅ Brief and submission data models")
    print("2. ✅ Brief commit message parsing ({briefId}:sub_1:{r2_link})")
    print("3. ✅ Database schema and operations (BriefDatabase class)")
    print("4. ✅ R2 storage client for video validation")
    print("5. ✅ Speed-based scoring algorithm")
    print("6. ✅ Selection-based scoring (top 10, final 3)")
    print("\nNext Steps (Week 2):")
    print("- Integrate brief processing into validator.py")
    print("- Add email notification system")
    print("- Implement deadline monitoring")
    print("- Create validation pipeline for R2 videos")


if __name__ == "__main__":
    main()