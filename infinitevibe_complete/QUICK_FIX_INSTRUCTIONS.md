# Quick Fix for Validator Setup Issues

## Issues Encountered
1. **Authentication Error**: GitHub HTTPS authentication failed
2. **Missing PM2**: Process manager not installed  
3. **Missing Dependencies**: uvicorn, fastapi, motor not installed
4. **Wrong Directory Structure**: Script assumed `/data` directory
5. **Missing .env File**: Environment variables not configured

## Fixed Setup Commands

Run this corrected setup script:

```bash
# Download and run the fixed setup
wget https://raw.githubusercontent.com/DeltaCompute24/valitesting89/main/fixed_setup.sh
chmod +x fixed_setup.sh
./fixed_setup.sh
```

Or manually:

### 1. Clone Repository (Fixed Authentication)
```bash
# Try SSH first (if you have SSH key)
git clone git@github.com:DeltaCompute24/valitesting89.git

# Or HTTPS with token (if you have GitHub token)
git clone https://github.com/DeltaCompute24/valitesting89.git

cd valitesting89
```

### 2. Setup Python Environment
```bash
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt

# Install additional dependencies
pip install uvicorn fastapi motor pymongo loguru httpx tabulate numpy bittensor
```

### 3. Create Environment File
```bash
cat > .env << 'EOF'
MONGODB_URI=mongodb://localhost:27017/
SERVICE_PLATFORM_TRACKER_URL=http://localhost:12001
SERVICE_AI_DETECTOR_URL=http://localhost:12002
SUBTENSOR_NETWORK=finney
NETUID=89
BOT_DETECTION_ENABLED=true
BOT_THRESHOLD=0.7
CONFIDENCE_THRESHOLD=0.5
EOF
```

### 4. Test Framework
```bash
# Test follower analysis
python examples/basic_usage.py

# Test validator integration
python src/validator_patch.py
```

### 5. Install PM2 (if needed)
```bash
# Install Node.js first if not available
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install PM2
npm install -g pm2
```

### 6. Create Service Scripts
```bash
# AI Detector
cat > start_ai_detector.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export $(cat .env | xargs)
python -m uvicorn tensorflix.services.ai_detector.app:app --host 0.0.0.0 --port 12002
EOF
chmod +x start_ai_detector.sh

# Platform Tracker
cat > start_tracker.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export $(cat .env | xargs)
python -m uvicorn tensorflix.services.platform_tracker.app:app --host 0.0.0.0 --port 12001
EOF
chmod +x start_tracker.sh

# Validator with Bot Detection
cat > start_validator.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export $(cat .env | xargs)
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

python -m neurons.validating \
  --netuid 89 \
  --wallet.hotkey default \
  --wallet.name subnet89_owner \
  --wallet.path ~/.bittensor/wallets/ \
  --subtensor.network finney \
  --logging.debug
EOF
chmod +x start_validator.sh
```

### 7. Start Services
```bash
# With PM2 (recommended)
pm2 start ./start_ai_detector.sh --name tensorflix-ai-detector
pm2 start ./start_tracker.sh --name tensorflix-tracker  
pm2 start ./start_validator.sh --name tensorflix-validator
pm2 save

# Or manually (for testing)
./start_ai_detector.sh &
./start_tracker.sh &
./start_validator.sh
```

### 8. Monitor Bot Detection
```bash
# Watch validator logs for bot detection activity
pm2 logs tensorflix-validator | grep -i "bot\|follower\|analysis"

# Check validator status
btcli subnets show --netuid 89
```

## Key Configuration

### Environment Variables
- `BOT_DETECTION_ENABLED=true` - Enable/disable bot detection
- `BOT_THRESHOLD=0.7` - Bot probability threshold (70%)
- `CONFIDENCE_THRESHOLD=0.5` - Minimum confidence to act (50%)

### Bot Detection Behavior
- Analyzes Instagram followers every 24 hours
- Applies penalties to engagement rates for accounts with >70% bot probability
- Reduces engagement rate by up to 80% for confirmed bot accounts
- Logs all detection activities to validator logs

### Monitoring
Look for these log messages:
- `🤖 Bot penalty applied to [hotkey]: 0.XX` - Penalty applied
- `Suspicious bot followers detected for [hotkey]` - Account flagged
- `Bot detection stats:` - Summary statistics

## Troubleshooting

### If Services Fail to Start
```bash
# Check Python path
which python
source .venv/bin/activate

# Check dependencies
pip list | grep -E "(uvicorn|fastapi|motor|bittensor)"

# Test imports
python -c "import uvicorn, fastapi, motor, bittensor; print('All imports OK')"
```

### If Bot Detection Not Working
```bash
# Check if framework loads
python -c "
import sys
sys.path.append('./src')
from validator_integration import ValidatorBotDetector
print('Bot detection framework loaded successfully')
"

# Check configuration
grep -E "BOT_|CONFIDENCE_" .env
```

### If Authentication Still Fails
```bash
# Use personal access token
git clone https://YOUR_TOKEN@github.com/DeltaCompute24/valitesting89.git

# Or download as ZIP
wget https://github.com/DeltaCompute24/valitesting89/archive/main.zip
unzip main.zip
mv valitesting89-main valitesting89
```

This should resolve all the issues encountered in the original setup.