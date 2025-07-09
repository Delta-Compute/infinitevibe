#!/bin/bash

# Platform Tracker Service startup script
echo "🌐 Starting Platform Tracker Service..."

# Navigate to the platform tracker directory
cd "$(dirname "$0")"

# Go back to project root to activate venv
cd ../../..

# Activate virtual environment
source .venv/bin/activate

# Load environment variables (filter out comments and empty lines)
export $(cat .env | grep -v "^#" | grep -v "^$" | xargs)

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

echo "   - Service URL: http://localhost:12001"
echo "   - Python path: $PYTHONPATH"
echo "   - Apify API Key: ${APIFY_API_KEY:0:15}..."
echo "   - MongoDB: $MONGODB_URI"
echo ""

# Start the platform tracker service
python tensorflix/services/platform_tracker/app.py