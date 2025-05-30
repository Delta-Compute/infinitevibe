# TensorFlix - Decentralized AI Video Production

A blockchain-coordinated system where miners create video content and validators score them based on their popular appeal.

## Overview

TensorFlix implements a decentralized content creation and validation pipeline:
- **Miners** submit video content to the SN and post the content on social media, and eventually the TensorFlix website
- **Validator**  score submissions by their engagement on the video traffic. Validators also: verify content is 100% AI generated, zero illicit content, traffic is real/not bots. 
- **Coordination** happens through Bittensor blockchain and GitHub gists

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Miners    │────▶│  Blockchain  │◀────│ Validators  │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                     │
       ▼                    ▼                     ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Submission  │     │Chain Syncer  │     │Task Gists   │
│   Gists     │     │   Service    │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  Platform    │
                    │  Tracker     │
                    └──────────────┘
```

## Quick Start

### Prerequisites

1. Install dependencies:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv
uv sync
source .venv/bin/activate
```

2. Set environment variables:
```bash
export YOUTUBE_API_KEY="your_youtube_api_key"
export APIFY_API_KEY="your_apify_api_key"  # For Instagram
export NETUID=89
export SUBTENSOR_NETWORK="mainnet"
```

### Start Core Services

1. **Chain Syncer** (tracks blockchain commits):
```bash
uvicorn tensorflix.services.chain_syncer.app:app --port 8001
```

2. **Platform Tracker** (fetches video/reel metrics):
```bash
uvicorn tensorflix.services.platform_tracker.app:app --port 8000
```

## For Validators

### 1. Create Task Challenges

Create a GitHub gist with your tasks (one JSON per line):
```json
{"task-id-1": {"description": "educate everyone about bittensor", "platform": "youtube", "start_at": "2025-01-25T12:00:00Z"}}
{"task-id-2": {"description": "create engaging AI tutorials", "platform": "youtube", "start_at": "2025-01-26T00:00:00Z"}}
{"task-id-3": {"description": "showcase Bittensor ecosystem", "platform": "instagram", "start_at": "2025-01-27T00:00:00Z"}}
```

### 2. Commit to Blockchain

```bash
python scripts/do_commit.py \
  --netuid 89 \
  --wallet-name validator_wallet \
  --wallet-hotkey validator_hotkey \
  --commit "your_github_username:your_gist_id" \
  --network mainnet
```

### 3. Run Validation Loop

```bash
python scripts/validator/run.py \
  --validator-gist-id your_gist_id \
  --validator-username your_github_username \
  --update-interval 24  # hours
```

The validator will:
- Fetch all miner submissions every 24 hours
- Update video/reel metrics
- Validate content (uniqueness, publish time)
- Calculate normalized scores based on views/hour
- Log top performers for each task

## For Miners

### 1. View Available Tasks

Check validator gists to see current challenges and their requirements.

### 2. Create Content

Produce videos/reels that match the task description. Content must be published **after** the task's `start_at` timestamp.

### 3. Submit Your Work

Create a GitHub gist with your submissions:
```json
{
  "submissions": [
    ["task-id-1", "dQw4w9WgXcQ"],
    ["task-id-2", "jNQXAC9IVRw"],
    ["task-id-3", "ABC123defGHI"]
  ]
}
```

Where:
- First element: Task ID from validator's gist
- Second element: Content ID (YouTube video ID or Instagram reel ID)

### 4. Commit to Blockchain

```bash
python scripts/do_commit.py \
  --netuid 89 \
  --wallet-name miner_wallet \
  --wallet-hotkey miner_hotkey \
  --commit "your_github_username:your_gist_id" \
  --network mainnet
```

## Validation Rules

### 1. **Uniqueness Check**
- Each content ID can only be submitted once per task
- First submission (by timestamp) gets credit

### 2. **Timestamp Validation**
- Content must be published after task's `start_at` time
- Pre-existing content is rejected

### 3. **Scoring Algorithm**
```python
score = view_count / hours_since_publish
normalized_score = score / max_score_in_task
```

Scores are normalized to [0, 1] range within each task.

## API Reference

### Chain Syncer (Port 8001)

**GET** `/get_all_peers_metadata`
- Returns all peer commits and metadata
- Used by validator to discover miner submissions

**GET** `/health`
- Service health check

### Platform Tracker (Port 8000)

**GET** `/youtube/video/{video_id}`
- Returns YouTube video metrics
- Response includes: view_count, like_count, comment_count, published_at

**GET** `/instagram/reel/{reel_id}`
- Returns Instagram reel metrics
- Response includes: video_view_count, like_count, comment_count, timestamp

## Data Formats

### Task Format (Validator Gist)
```json
{
  "unique-task-id": {
    "description": "Clear description of what content should achieve",
    "platform": "youtube|instagram",
    "start_at": "2025-01-25T12:00:00Z"
  }
}
```

### Submission Format (Miner Gist)
```json
{
  "submissions": [
    ["task-id", "content-id"],
    ["task-id", "content-id"]
  ]
}
```

### Blockchain Commit Format
```
username:gist_id
```

## Monitoring & Logs

The validator creates detailed logs:
- `video_topic_validator.log` - Full validation details
- Console output shows:
  - Update cycle progress
  - Task and submission counts
  - Top performers per task
  - Validation failures

## Best Practices

### For Validators
- Create clear, specific task descriptions
- Set reasonable start times (allow miners time to see tasks)
- Run validator continuously for consistent scoring
- Monitor logs for system health

### For Miners
- Check tasks frequently for new opportunities
- Create high-quality, engaging content
- Submit promptly after publishing
- Ensure content matches task requirements

## Troubleshooting

### Common Issues

1. **"No video data found"**
   - Check content ID is correct
   - Ensure content is public
   - Verify API keys are valid

2. **"Published before task start"**
   - Content must be created after task announcement
   - Check task's `start_at` timestamp

3. **"Duplicate submission"**
   - Each content ID can only be used once per task
   - Create unique content for each submission

4. **Services not responding**
   - Ensure chain syncer is running on port 8001
   - Ensure platform tracker is running on port 8000
   - Check firewall settings

### Debug Commands

Check service health:
```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
```

Test video data fetch:
```bash
curl http://localhost:8000/youtube/video/VIDEO_ID
```

View all peer metadata:
```bash
curl http://localhost:8001/get_all_peers_metadata | jq
```

## Security Considerations

- Keep wallet keys secure
- Use public gists only (private gists won't work)
- Don't share API keys
- Monitor for suspicious submissions

## Support

For issues or questions:
- Check logs for detailed error messages
- Ensure all services are running
- Verify gist formats match examples
- Confirm blockchain transactions succeeded
