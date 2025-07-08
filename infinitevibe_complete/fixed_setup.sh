#!/bin/bash

# Fixed Setup Script for TensorFlix SN89 Validator
# Execute these commands to integrate follower analysis framework

echo "🚦 Starting TensorFlix Validator Setup (Fixed Version)..."

# 1. Find current working directory and setup
echo "📍 Current location: $(pwd)"
echo "👤 Current user: $(whoami)"

# 2. Clone the repository with SSH (better than HTTPS)
echo "📥 Cloning codebase..."
if [ ! -d "valitesting89" ]; then
    # Try SSH first, fallback to HTTPS
    git clone git@github.com:DeltaCompute24/valitesting89.git || \
    git clone https://github.com/DeltaCompute24/valitesting89.git
fi

cd valitesting89 || {
    echo "❌ Failed to enter valitesting89 directory"
    exit 1
}

echo "✅ Successfully cloned and entered repository"

# 3. Setup Python environment
echo "🔧 Setting up Python environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install basic requirements first
echo "📦 Installing basic Python packages..."
pip install --upgrade pip

# Install the project requirements
echo "📦 Installing project requirements..."
pip install -r requirements.txt

# Install additional dependencies needed for the validator
echo "📦 Installing additional dependencies..."
pip install uvicorn fastapi motor pymongo loguru httpx asyncio-motor tabulate numpy

# Install bittensor
echo "📦 Installing bittensor..."
pip install bittensor

# 4. Install PM2 if not available
echo "📦 Checking PM2 installation..."
if ! command -v pm2 &> /dev/null; then
    echo "Installing PM2..."
    if command -v npm &> /dev/null; then
        npm install -g pm2
    else
        echo "⚠️  PM2 not installed and npm not available"
        echo "   You'll need to run services manually or install PM2"
    fi
else
    echo "✅ PM2 already installed"
fi

# 5. Create environment file template
echo "⚙️ Creating environment configuration..."
cat > .env << 'EOF'
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/

# Service URLs
SERVICE_PLATFORM_TRACKER_URL=http://localhost:12001
SERVICE_AI_DETECTOR_URL=http://localhost:12002

# Bittensor Configuration
SUBTENSOR_NETWORK=finney
NETUID=89

# Follower Analysis Configuration
BOT_DETECTION_ENABLED=true
BOT_THRESHOLD=0.7
CONFIDENCE_THRESHOLD=0.5
EOF

echo "✅ Created .env file - please review and update as needed"

# 6. Test the follower analysis framework
echo "🧪 Testing follower analysis framework..."
python examples/basic_usage.py

# 7. Test validator patch
echo "🧪 Testing validator integration..."
python src/validator_patch.py

# 8. Create service scripts
echo "📝 Creating service scripts..."

# AI Detector Service
cat > start_ai_detector.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export $(cat .env | xargs)
python -m uvicorn tensorflix.services.ai_detector.app:app --host 0.0.0.0 --port 12002
EOF
chmod +x start_ai_detector.sh

# Platform Tracker Service  
cat > start_tracker.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export $(cat .env | xargs)
python -m uvicorn tensorflix.services.platform_tracker.app:app --host 0.0.0.0 --port 12001
EOF
chmod +x start_tracker.sh

# Validator Service with Bot Detection
cat > start_validator.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export $(cat .env | xargs)

# Add the follower analysis path to Python path
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

# 9. Test services individually (if dependencies are available)
echo "🧪 Testing services..."

if python -c "import uvicorn" 2>/dev/null; then
    echo "✅ uvicorn available, testing services..."
    
    # Test AI detector
    echo "Testing AI detector..."
    timeout 5s ./start_ai_detector.sh &
    sleep 3
    if curl -s http://localhost:12002/health >/dev/null 2>&1; then
        echo "✅ AI Detector OK"
    else
        echo "⚠️  AI Detector not responding (may need dependencies)"
    fi
    pkill -f "uvicorn.*ai_detector" 2>/dev/null || true
    
    # Test platform tracker
    echo "Testing platform tracker..."
    timeout 5s ./start_tracker.sh &
    sleep 3
    if curl -s http://localhost:12001/health >/dev/null 2>&1; then
        echo "✅ Platform Tracker OK"
    else
        echo "⚠️  Platform Tracker not responding (may need dependencies)"
    fi
    pkill -f "uvicorn.*platform_tracker" 2>/dev/null || true
else
    echo "⚠️  uvicorn not available, skipping service tests"
fi

# 10. Setup PM2 services (if PM2 is available)
if command -v pm2 &> /dev/null; then
    echo "🚀 Setting up PM2 services..."
    
    # Stop any existing services
    pm2 delete tensorflix-ai-detector tensorflix-tracker tensorflix-validator 2>/dev/null || true
    
    # Start new services
    pm2 start ./start_ai_detector.sh --name tensorflix-ai-detector
    pm2 start ./start_tracker.sh --name tensorflix-tracker
    pm2 start ./start_validator.sh --name tensorflix-validator
    
    pm2 save
    pm2 list
    
    echo "📊 Services started with PM2"
else
    echo "⚠️  PM2 not available - you can run services manually:"
    echo "   ./start_ai_detector.sh &"
    echo "   ./start_tracker.sh &"
    echo "   ./start_validator.sh"
fi

# 11. Final status
echo ""
echo "🎉 Setup complete!"
echo ""
echo "📁 Repository location: $(pwd)"
echo "🐍 Python environment: $(which python)"
echo "📊 Follower Analysis: Ready"
echo ""
echo "🔧 Next steps:"
echo "1. Review and update .env file with your configuration"
echo "2. Ensure MongoDB is running (connection: $MONGODB_URI)"
echo "3. Set up your Bittensor wallet if not already done"
echo "4. Start services:"
if command -v pm2 &> /dev/null; then
    echo "   pm2 start tensorflix-validator"
    echo "   pm2 logs tensorflix-validator"
else
    echo "   ./start_validator.sh"
fi
echo ""
echo "🔍 Monitor logs for follower analysis activity:"
echo "   Look for messages like '🤖 Bot penalty applied' in validator logs"
echo ""
echo "📚 Integration guide: VALIDATOR_INTEGRATION.md"