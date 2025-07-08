#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export $(cat .env | xargs)
python -m uvicorn tensorflix.services.ai_detector.app:app --host 0.0.0.0 --port 12002
