#!/usr/bin/env python3
"""
Miner Submissions Report Generator
Parses validator logs and generates a comprehensive report of all miner submissions.
"""

import json
import re
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any
import argparse


def parse_validator_logs(log_content: str) -> Dict[str, Any]:
    """Parse validator logs to extract miner submissions and engagement data."""
    
    # Extract engagement rates from logs
    engagement_pattern = r"engagement_rates.*?({.*?})"
    engagement_matches = re.findall(engagement_pattern, log_content, re.DOTALL)
    
    # Extract submission data
    submission_pattern = r"submissions.*?({.*?})"
    submission_matches = re.findall(submission_pattern, log_content, re.DOTALL)
    
    # Parse latest engagement rates
    latest_engagement = {}
    if engagement_matches:
        try:
            # Get the last engagement rates entry
            latest_engagement_str = engagement_matches[-1]
            # Clean up the string and parse as JSON
            cleaned = latest_engagement_str.replace("'", '"')
            latest_engagement = json.loads(cleaned)
        except:
            pass
    
    # Parse all submissions
    all_submissions = defaultdict(list)
    for match in submission_matches:
        try:
            cleaned = match.replace("'", '"')
            submissions_data = json.loads(cleaned)
            for hotkey, submissions in submissions_data.items():
                if isinstance(submissions, list):
                    all_submissions[hotkey].extend(submissions)
                else:
                    all_submissions[hotkey].append(submissions)
        except:
            continue
    
    return {
        'engagement_rates': latest_engagement,
        'submissions': dict(all_submissions)
    }


def get_platform_link(platform: str, content_id: str, content_type: str = None) -> str:
    """Generate platform links based on content ID and platform."""
    if platform == "youtube":
        return f"https://www.youtube.com/watch?v={content_id}"
    elif platform == "instagram":
        if content_type == "post":
            return f"https://www.instagram.com/p/{content_id}"
        elif content_type == "reel":
            return f"https://www.instagram.com/reel/{content_id}"
        else:
            return f"https://www.instagram.com/p/{content_id}"
    return f"Unknown platform: {platform}"


def generate_report(data: Dict[str, Any]) -> str:
    """Generate a comprehensive markdown report from parsed data."""
    
    report = []
    report.append("# Miner Submissions Report")
    report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Top performers section
    engagement_rates = data.get('engagement_rates', {})
    if engagement_rates:
        report.append("## Top Performers by Engagement Rate")
        report.append("")
        
        # Sort by engagement rate
        sorted_miners = sorted(engagement_rates.items(), key=lambda x: x[1], reverse=True)
        
        for i, (hotkey, rate) in enumerate(sorted_miners[:10], 1):
            report.append(f"{i}. **{hotkey[-12:]}...** - {rate:.4f}% engagement")
        
        report.append("")
    
    # All submissions section
    submissions = data.get('submissions', {})
    if submissions:
        report.append("## All Miner Submissions")
        report.append("")
        
        total_submissions = sum(len(subs) for subs in submissions.values())
        report.append(f"**Total Submissions:** {total_submissions}")
        report.append(f"**Active Miners:** {len(submissions)}")
        report.append("")
        
        # Platform statistics
        platform_stats = defaultdict(int)
        for miner_subs in submissions.values():
            for sub in miner_subs:
                if isinstance(sub, dict) and 'platform' in sub:
                    platform_stats[sub['platform']] += 1
        
        if platform_stats:
            report.append("### Platform Distribution")
            for platform, count in sorted(platform_stats.items()):
                report.append(f"- **{platform}:** {count} submissions")
            report.append("")
        
        # Detailed submissions by miner
        report.append("### Detailed Submissions by Miner")
        report.append("")
        
        for hotkey, miner_submissions in submissions.items():
            if not miner_submissions:
                continue
                
            engagement_rate = engagement_rates.get(hotkey, 0)
            report.append(f"#### Miner: {hotkey[-12:]}...")
            report.append(f"**Full Hotkey:** `{hotkey}`")
            report.append(f"**Engagement Rate:** {engagement_rate:.4f}%")
            report.append(f"**Total Submissions:** {len(miner_submissions)}")
            report.append("")
            
            for i, submission in enumerate(miner_submissions, 1):
                if not isinstance(submission, dict):
                    continue
                    
                platform = submission.get('platform', 'unknown')
                content_id = submission.get('content_id', 'unknown')
                content_type = submission.get('content_type', '')
                
                # Generate platform link
                try:
                    link = get_platform_link(platform, content_id, content_type)
                except:
                    link = f"Content ID: {content_id}"
                
                report.append(f"**Submission {i}:**")
                report.append(f"- Platform: {platform}")
                report.append(f"- Content ID: {content_id}")
                report.append(f"- Link: [{link}]({link})")
                
                # Add additional metadata if available
                if 'ai_score' in submission:
                    report.append(f"- AI Score: {submission['ai_score']}")
                if 'view_count' in submission:
                    report.append(f"- Views: {submission['view_count']:,}")
                if 'like_count' in submission:
                    report.append(f"- Likes: {submission['like_count']:,}")
                if 'comment_count' in submission:
                    report.append(f"- Comments: {submission['comment_count']:,}")
                
                report.append("")
            
            report.append("---")
            report.append("")
    
    else:
        report.append("No submissions found in the provided logs.")
        report.append("")
    
    # Summary section
    report.append("## Summary")
    report.append("")
    if submissions:
        report.append(f"This report contains data for {len(submissions)} active miners with a total of {sum(len(subs) for subs in submissions.values())} submissions.")
        if engagement_rates:
            top_performer = max(engagement_rates.items(), key=lambda x: x[1])
            report.append(f"Top performer: {top_performer[0][-12:]}... with {top_performer[1]:.4f}% engagement rate.")
    else:
        report.append("No miner submission data was found in the provided logs.")
    
    report.append("")
    report.append("---")
    report.append("*Report generated by InfiniteVibe Validator Analytics*")
    
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description='Generate miner submissions report from validator logs')
    parser.add_argument('--log-file', '-l', help='Path to validator log file')
    parser.add_argument('--output', '-o', default='miner_submissions_report.md', help='Output file path')
    
    args = parser.parse_args()
    
    if args.log_file:
        try:
            with open(args.log_file, 'r') as f:
                log_content = f.read()
        except FileNotFoundError:
            print(f"Error: Log file {args.log_file} not found")
            return
        except Exception as e:
            print(f"Error reading log file: {e}")
            return
    else:
        # Sample log content for demonstration
        log_content = """
        Sample validator logs would go here. 
        The script will parse engagement_rates and submissions data from PM2 logs.
        """
        print("No log file provided. Use --log-file to specify validator logs.")
        print("Example usage: python miner_submissions_report.py --log-file ~/.pm2/logs/tensorflix-validator-out.log")
        return
    
    # Parse the logs
    data = parse_validator_logs(log_content)
    
    # Generate report
    report = generate_report(data)
    
    # Save report
    try:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report generated successfully: {args.output}")
    except Exception as e:
        print(f"Error writing report: {e}")


if __name__ == "__main__":
    main()