#!/bin/bash
cd /data/valitesting89/infinitevibe_complete
source .venv/bin/activate
export $(cat .env | xargs)
python src/background_follower_analyzer.py
