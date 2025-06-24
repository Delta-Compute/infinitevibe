#!/bin/bash

set -e

# Store current git HEAD
current_commit=$(git rev-parse HEAD)

# Fetch latest changes
git fetch origin main

# Get the latest commit on remote
latest_commit=$(git rev-parse origin/main)

# Compare commits
if [ "$current_commit" != "$latest_commit" ]; then
    echo "[INFO] New updates found. Pulling latest code..."
    git pull origin main

    echo "[INFO] Syncing virtual environment..."
    uv sync
    source .venv/bin/activate

    echo "[INFO] Restarting PM2 services..."
    pm2 restart tensorflix-tracker
    pm2 restart tensorflix-ai-detector
    pm2 restart tensorflix-validator

    echo "[SUCCESS] Update completed and PM2 services restarted."
else
    echo "[INFO] No updates found. Nothing to do."
fi

# Exit cleanly with success status
exit 0