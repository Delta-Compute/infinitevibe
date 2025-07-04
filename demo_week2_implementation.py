#!/usr/bin/env python3
"""
Demonstration of Week 2 implementation - validator integration with brief system.
Shows the complete flow of brief submission processing.
"""

import asyncio
from datetime import datetime, timedelta
from tensorflix.models.brief import (
    Brief, BriefSubmission, BriefStatus, 
    SubmissionType, ValidationStatus, BriefCommitMessage
)
from tensorflix.protocol import PeerMetadata
from tensorflix.utils.ids import generate_brief_id
from tensorflix.services.email_notifier import EmailNotifier


def demo_validator_brief_integration():
    """Demonstrate how the validator now handles brief submissions."""
    print("=== Validator Brief Integration ===\n")
    
    # Simulate a miner with brief commit
    test_commits = [
        "brief_20241204_abc123:sub_1:https://r2.storage/video1.mp4",
        "john:gist123456",  # Traditional format
        "brief_20241204_abc123:sub_2:https://r2.storage/revision.mp4"
    ]
    
    print("✅ Commit Message Processing:")
    for commit in test_commits:
        peer = PeerMetadata(uid=1, hotkey="5Eg2TvA5G4f7K9Kj6Vn89Lm3Qw2Rs1Tx9Yz8", commit=commit)
        
        if peer.brief_commit:
            print(f"   BRIEF: {commit}")
            print(f"   → Will process as brief submission: {peer.brief_commit.brief_id}")
            print(f"   → Type: {peer.brief_commit.submission_type}")
        else:
            print(f"   GIST:  {commit}")
            print(f"   → Will process as traditional gist submission")
        print()


def demo_scoring_system():
    """Demonstrate the hybrid scoring system."""
    print("=== Hybrid Scoring System ===\n")
    
    # Mock scores
    engagement_scores = {
        "miner1": 25.4,  # High engagement
        "miner2": 12.8,  # Medium engagement
        "miner3": 8.2,   # Low engagement
    }
    
    brief_scores = {
        "miner1": 85.0,  # Good brief performance
        "miner2": 92.0,  # Excellent brief performance
        "miner4": 78.0,  # Only brief, no engagement
    }
    
    print("✅ Individual Scores:")
    print("   Engagement Scores:")
    for miner, score in engagement_scores.items():
        print(f"     {miner}: {score:.1f}%")
    
    print("\n   Brief Scores:")
    for miner, score in brief_scores.items():
        print(f"     {miner}: {score:.1f}/100")
    
    # Calculate combined scores (70% engagement, 30% brief)
    all_miners = set(engagement_scores.keys()) | set(brief_scores.keys())
    combined_scores = {}
    
    print("\n✅ Combined Scores (70% engagement + 30% brief):")
    for miner in all_miners:
        eng_score = engagement_scores.get(miner, 0)
        brief_score = brief_scores.get(miner, 0)
        combined = (eng_score * 0.7) + (brief_score * 0.3)
        combined_scores[miner] = combined
        
        print(f"   {miner}: {combined:.1f} ({eng_score:.1f}*0.7 + {brief_score:.1f}*0.3)")
    
    # Show ranking
    ranked = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
    print(f"\n✅ Final Ranking:")
    for i, (miner, score) in enumerate(ranked, 1):
        print(f"   {i}. {miner}: {score:.1f}")


def demo_brief_lifecycle():
    """Demonstrate a complete brief lifecycle."""
    print("\n\n=== Brief Lifecycle Demo ===\n")
    
    # 1. Brief creation
    brief_id = generate_brief_id()
    brief = Brief(
        brief_id=brief_id,
        user_email="creator@infinitevibe.ai",
        title="Create a futuristic city AI video",
        description="30-second video showcasing a futuristic smart city with AI integration",
        requirements="1080p, MP4, 30 seconds, futuristic theme"
    )
    
    print("✅ 1. Brief Created:")
    print(f"   ID: {brief.brief_id}")
    print(f"   Title: {brief.title}")
    print(f"   6hr deadline: {brief.deadline_6hr}")
    print(f"   24hr deadline: {brief.deadline_24hr}")
    
    # 2. Miner submissions
    print("\n✅ 2. Miner Submissions:")
    miners = [
        ("5Eg2TvA5G4f7K9Kj6Vn89Lm3Qw2Rs1Tx9Yz8", 1),  # 1 hour after
        ("5Fg3QwB6H5g8L2Pn4Km7Vx9Rt1Qs3Wy5Ez2", 3),  # 3 hours after
        ("5Hg4RxC7I6h9M3Qo5Ln8Wy0Su2Pt4Xz6Fa3", 8),  # 8 hours after
    ]
    
    submissions = []
    for hotkey, hours_after in miners:
        commit_msg = f"{brief_id}:sub_1:https://r2.storage/{hotkey[-8:]}.mp4"
        
        # Simulate validator processing
        print(f"   Validator receives: {commit_msg}")
        
        brief_commit = BriefCommitMessage.parse(commit_msg)
        if brief_commit:
            submission = BriefSubmission(
                submission_id=f"{brief_id}_{hotkey[-8:]}_sub_1",
                brief_id=brief_id,
                miner_hotkey=hotkey,
                submission_type=SubmissionType.SUB_1,
                r2_link=brief_commit.r2_link,
                submitted_at=brief.created_at + timedelta(hours=hours_after),
                validation_status=ValidationStatus.VALID
            )
            submissions.append(submission)
            
            speed_score = submission.calculate_speed_score(brief)
            print(f"     → Processed: {hotkey[-8:]} - Speed score: {speed_score:.1f}/30")
    
    # 3. Top 10 selection (simulate user selection)
    print("\n✅ 3. Top 10 Selection (after 6 hours):")
    brief.top_10_miners = [sub.miner_hotkey for sub in submissions[:2]]
    brief.status = BriefStatus.SELECTING_TOP10
    
    for submission in submissions:
        selection_score = submission.calculate_selection_score(brief)
        total_score = submission.calculate_total_score(brief)
        status = "SELECTED" if submission.miner_hotkey in brief.top_10_miners else "NOT SELECTED"
        print(f"   {submission.miner_hotkey[-8:]}: {total_score:.1f} total - {status}")
    
    # 4. Final selection
    print("\n✅ 4. Final Selection:")
    brief.final_3_miners = [submissions[0].miner_hotkey]
    brief.status = BriefStatus.COMPLETED
    
    print("   Final scoring:")
    for submission in submissions:
        final_score = submission.calculate_total_score(brief)
        if submission.miner_hotkey in brief.final_3_miners:
            print(f"   🥇 {submission.miner_hotkey[-8:]}: {final_score:.1f} - WINNER")
        elif submission.miner_hotkey in brief.top_10_miners:
            print(f"   🥈 {submission.miner_hotkey[-8:]}: {final_score:.1f} - Top 10")
        else:
            print(f"   🥉 {submission.miner_hotkey[-8:]}: {final_score:.1f} - Participant")


async def demo_email_notifications():
    """Demonstrate email notification system."""
    print("\n\n=== Email Notification System ===\n")
    
    emailer = EmailNotifier()
    
    # Create a sample brief
    brief = Brief(
        brief_id="brief_20241204_demo123",
        user_email="user@example.com",
        title="Demo Brief",
        description="This is a demo brief for testing"
    )
    
    print("✅ Email Notifications Available:")
    print("   1. Brief confirmation to user")
    print("   2. New brief notification to miners")
    print("   3. Deadline reminders")
    print("   4. Top 10 selection ready")
    print("   5. Top 10 notifications to selected miners")
    
    # Demo brief confirmation
    print(f"\n✅ Demo: Brief Confirmation Email")
    success = await emailer.send_brief_confirmation(brief)
    print(f"   Sent confirmation email: {success}")
    
    # Demo deadline reminder
    print(f"\n✅ Demo: Deadline Reminder")
    miner_emails = ["miner1@example.com", "miner2@example.com"]
    success = await emailer.send_deadline_reminder(brief, miner_emails)
    print(f"   Sent deadline reminders: {success}")


def main():
    """Run all Week 2 demonstrations."""
    print("InfiniteVibe Week 2 Implementation Demo")
    print("=" * 50)
    print("\nValidator Integration with Brief System")
    print("Demonstrates the complete brief processing pipeline.\n")
    
    # Run demos
    demo_validator_brief_integration()
    demo_scoring_system()
    demo_brief_lifecycle()
    
    # Run async email demo
    asyncio.run(demo_email_notifications())
    
    print("\n" + "=" * 50)
    print("✅ Week 2 Implementation Complete!\n")
    print("Key Features Integrated:")
    print("1. ✅ Brief submission processing in validator")
    print("2. ✅ R2 storage validation pipeline")
    print("3. ✅ Hybrid scoring system (engagement + briefs)")
    print("4. ✅ Deadline monitoring and reminders")
    print("5. ✅ Email notification system foundation")
    print("6. ✅ GCP processing pipeline hooks")
    
    print("\nValidator Changes:")
    print("- Detects brief vs gist commits automatically")
    print("- Validates R2 video submissions")
    print("- Enforces brief deadlines and top 10 permissions")
    print("- Combines engagement and brief scores for ranking")
    print("- Monitors deadlines for email reminders")
    
    print("\nNext Steps (Week 3):")
    print("- Add actual email provider integration")
    print("- Implement GCP Cloud Run job integration")
    print("- Create web dashboard for brief management")
    print("- Add comprehensive testing and monitoring")


if __name__ == "__main__":
    main()