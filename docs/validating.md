# Setup Guide for Validating

## Hardware Requirements
- CPU: >= 4 cores
- RAM: >= 8GB
- Disk: >= 100GB
- OS: Linux

## API Keys
- Apify API Key at [Apify](https://docs.apify.com/api/v2)
   - Apify is used for fetching instagram metrics and download videos from social media. Not free.
   - Register for actors:
      - Get instagram post statistics [Instagram API Scraper](https://console.apify.com/actors/RB9HEZitC8hIUXAha)
      - Get youtube video statistics [Youtube API Scraper](https://console.apify.com/actors/h7sDV53CddomktSi5)
      - Download videos from social media [All-In-One Media Downloader](https://console.apify.com/actors/iZbsVYT4VfdMxoIPL)
   - Youtube API Key will be used for free fetching youtube video metrics.
- Get SightEngine API Key & API User from [SightEngine](https://dashboard.sightengine.com/api-credentials)


## Run MongoDB locally

1. Install Docker Engine: [Docker Engine](https://docs.docker.com/engine/install)

2. Run MongoDB

```bash
docker pull mongodb/mongodb-community-server:latest
docker run --name mongodb -p 27017:27017 -d mongodb/mongodb-community-server:latest
```

## Environment Variables
- Create a `.env` file in the root of the repository

```bash
APIFY_API_KEY=your_apify_api_key
YOUTUBE_API_KEY=your_youtube_api_key
MONGODB_URI=mongodb://localhost:27017/
SIGHTENGINE_USER=your_sightengine_user
SIGHTENGINE_SECRET=your_sightengine_secret
```

## Setup

1. Clone the repository

```bash
git clone https://github.com/Delta-Compute/infinitevibe
```

2. Install dependencies

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv
uv sync
source .venv/bin/activate
apt update && apt upgrade -y && apt-get install -y nano git python3-pip jq npm && npm install pm2 -g && pm2 update
```

3. Run services that support the validator

```bash
pm2 start --name "tensorflix-tracker" "uvicorn tensorflix.services.platform_tracker.app:app --host 0.0.0.0 --port 12001"
pm2 start --name "tensorflix-ai-detector" "uvicorn tensorflix.services.ai_detector.app:app --host 0.0.0.0 --port 12002"
```

4. Run the validator

```bash
pm2 start --name "tensorflix-validator" "python -m neurons.validating \
--netuid 89 \
--wallet-hotkey <your_hotkey> \
--wallet-name <your_wallet_name> \
--subtensor-network finney"
```

5. Run script that upgrade the validator automatically

```bash
pm2 start validator_upgrade.sh --name tensorflix-vali-updater --cron "0/30 * * * *" --interpreter /bin/bash --no-autorestart
```
