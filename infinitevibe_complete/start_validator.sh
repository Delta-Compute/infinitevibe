#!/bin/bash
cd /data/valitesting89/infinitevibe_complete
source .venv/bin/activate
export $(cat .env | xargs)

python -m neurons.validating \
  --netuid 89 \
  --wallet.name subnet89_owner \
  --wallet.hotkey default \
  --wallet.path /home/whit/.bittensor/wallets/ \
  --subtensor.network finney \
  --logging.debug
