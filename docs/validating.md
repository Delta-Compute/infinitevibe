# Setup Guide for Validating

## Hardware Requirements
- CPU: >= 4 cores
- RAM: >= 8GB
- Disk: >= 100GB
- OS: Linux

## API Keys
- Apify API Key at [Apify](https://docs.apify.com/api/v2)
   - Apify is used for fetching instagram metrics and download videos from social media. Not free.
- YouTube API Key from Google Cloud Console. See [Youtube Tutorial](https://www.youtube.com/watch?v=uz7dY8qTFJw)
   - Youtube API Key will be used for free fetching youtube video metrics.

## Run MongoDB locally

1. Install Docker Engine

```bash
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove $pkg; done
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world
```

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
```

## Setup

1. Clone the repository

```bash
git clone https://github.com/Delta-Compute/tensorflix
```

2. Install dependencies

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv
uv sync
source .venv/bin/activate
```

3. Run the validator

```bash
python neurons/validating.py \
--netuid 89 \
--wallet-hotkey <your_hotkey> \
--wallet-name <your_wallet_name> \
--subtensor-network finney
```