#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate

# Load environment variables safely (filter out comments)
set -a
while IFS='=' read -r key value; do
    if [[ ! "$key" =~ ^# ]] && [[ -n "$key" ]]; then
        export "$key=$value"
    fi
done < .env
set +a

python -m uvicorn tensorflix.services.platform_tracker.app:app --host 0.0.0.0 --port 12001
