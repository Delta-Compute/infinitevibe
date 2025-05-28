# TensorFlix MVP Pipeline

A simple pipeline where miners submit YouTube videos and validators check them using blockchain coordination.

## What it does

- **Miners**: Submit YouTube video IDs for tasks
- **Validators**: Create tasks and validate submissions
- **Services**: Track blockchain data and fetch video info

## Setup

### Install dependencies
```bash
pip install -r requirements.txt
```

### Set environment variables
```bash
export YOUTUBE_API_KEY="your_api_key"
export NETUID=89
export SUBTENSOR_NETWORK="mainnet"
```

## Running the system

### 1. Start services

Start chain syncer (tracks blockchain):
```bash
uvicorn tensorflix.services.chain_syncer.app:app --port 8001
```

Start platform tracker (gets YouTube data):
```bash
uvicorn tensorflix.services.platform_tracker.app:app --port 8000
```

### 2. For Miners

Create a GitHub gist with your submissions:
```json
{
  "submissions": [
    ["task1", "youtube_video_id1"],
    ["task2", "youtube_video_id2"]
  ]
}
```

Example: https://gist.github.com/toilaluan/671296b3465daf4fcafafcb438f67f64

Commit your gist to blockchain:
```bash
python scripts/do_commit.py \
  --netuid 89 \
  --wallet-name your_wallet \
  --wallet-hotkey your_hotkey \
  --commit "your_username:your_gist_id" \
  --network mainnet
```

### 3. For Validators

Create a GitHub gist with tasks:
```json
{
  "task1": {
    "description": "educate about bittensor",
    "platform": "youtube"
  },
  "task2": {
    "description": "educate about bitcoin", 
    "platform": "youtube"
  }
}

Example: https://gist.github.com/toilaluan/cdc3b8166f8f6bc5dd8f70fd84d343c7
```

Commit your task gist:
```bash
python scripts/do_commit.py \
  --netuid 89 \
  --wallet-name validator_wallet \
  --wallet-hotkey validator_hotkey \
  --commit "validator_username:task_gist_id" \
  --network mainnet
```

Run the validator:
```bash
python scripts/validator/run.py
```

Example logs: [logs.txt](task_processor.log)

## How it works

1. Validators post tasks in a gist and commit the gist ID to blockchain
2. Miners see tasks and submit video IDs in their own gist
3. Miners commit their gist ID to blockchain
4. Validator script reads all submissions and validates them
5. Video data is fetched from YouTube API for validation

## API endpoints

Chain syncer (port 8001):
- `GET /get_all_peers_metadata` - Get all miner submissions
- `GET /health` - Check if service is running

Platform tracker (port 8000):
- `GET /youtube/video/{video_id}` - Get video details
- `GET /health` - Check if service is running

## File formats

Miner gist format:
```json
{
  "submissions": [
    ["task_id", "video_id"]
  ]
}
```

Validator gist format:
```json
{
  "task_id": {
    "description": "What you want",
    "criteria": "How to judge it"
  }
}
```

## Troubleshooting

- Make sure both services are running on ports 8000 and 8001
- Check your YouTube API key is valid
- Make sure gists are public
- Check wallet has funds for blockchain transactions
