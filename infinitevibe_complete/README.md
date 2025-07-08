# InfiniteVibe Testing Repository

This repository contains the complete InfiniteVibe subnet codebase plus the new Follower Analysis Framework for testing bot detection integration.

## 🔬 Testing Repository Contents

### Original InfiniteVibe Subnet
- `tensorflix/` - Core validator and protocol code
- `neurons/` - Mining and validating neurons
- `docs/` - Original subnet documentation

### New: Follower Analysis Framework
- `src/analyzers/` - Bot detection algorithms
- `src/detector.py` - Main detection engine  
- `src/validator_integration.py` - Validator integration
- `VALIDATOR_INTEGRATION.md` - Integration guide

---

# InfiniteVibe Follower Analysis Framework

An open-source, modular framework for detecting bot followers on Instagram accounts. Built for the InfiniteVibe subnet to help miners identify and mitigate fake follower attacks.

## 🎯 Purpose

This framework addresses the vulnerability in the InfiniteVibe mining reward system where fake followers can manipulate engagement rates. By providing miners with tools to detect and report bot followers, we maintain the integrity of the reward distribution system.

## 🏗️ Architecture

The framework uses a modular design that allows the community to contribute new detection algorithms:

```
follower-analysis/
├── src/
│   ├── analyzers/
│   │   ├── base.py          # Abstract base class for analyzers
│   │   ├── statistical.py   # Statistical pattern analysis
│   │   └── temporal.py      # Time-based pattern analysis
│   └── detector.py          # Main detection engine
├── tests/                   # Unit tests
├── examples/                # Usage examples
└── docs/                    # Documentation
```

## 🚀 Quick Start

### Basic Usage

```python
from analyzers.base import FollowerData
from detector import ModularBotDetector
from datetime import datetime, timedelta

# Create detector
detector = ModularBotDetector()

# Prepare follower data
followers = [
    FollowerData(
        username="john_doe",
        follower_count=1000,
        following_count=500,
        posts_count=50,
        bio="Photography enthusiast 📸",
        profile_picture_url="https://example.com/pic.jpg",
        is_verified=False,
        is_business=False,
        is_private=False,
        account_creation_date=datetime.now() - timedelta(days=365),
        last_post_date=datetime.now() - timedelta(days=5),
        location="New York, NY",
        external_url="https://johndoe.com"
    )
    # ... more followers
]

# Analyze followers
result = detector.analyze(followers)

print(f"Bot Probability: {result.bot_probability:.3f}")
print(f"Risk Level: {result.risk_level}")
print(f"Flags: {result.flags}")
```

### Running the Example

```bash
cd follower-analysis
python examples/basic_usage.py
```

### Running Tests

```bash
cd follower-analysis
python -m pytest tests/
```

## 🔍 Detection Methods

### Statistical Analyzer
- **Username Entropy**: Detects randomly generated usernames
- **Follower Ratios**: Identifies suspicious following patterns
- **Profile Completeness**: Checks for missing bios, photos, posts
- **Geographic Clustering**: Detects unusual location distributions

### Temporal Analyzer
- **Account Age Distribution**: Identifies bulk account creation
- **Creation Clustering**: Detects accounts created in suspicious timeframes
- **Activity Patterns**: Analyzes posting frequency and timing

## 🤝 Contributing New Analyzers

### 1. Create Your Analyzer

```python
from analyzers.base import BaseAnalyzer, FollowerData, AnalyzerResult

class MyCustomAnalyzer(BaseAnalyzer):
    def __init__(self):
        super().__init__("My Custom Analyzer", "1.0.0")
    
    def get_required_fields(self):
        return ["username", "follower_count"]
    
    def analyze(self, followers_data):
        # Your detection logic here
        score = self.calculate_authenticity_score(followers_data)
        
        return AnalyzerResult(
            analyzer_name=self.name,
            authenticity_score=score,
            confidence=0.8,
            details={"my_metric": score},
            flags=["suspicious_pattern"] if score < 0.5 else []
        )
```

### 2. Register with Detector

```python
detector = ModularBotDetector()
detector.register_analyzer("my_custom", MyCustomAnalyzer(), weight=0.3)
```

### 3. Submit Your Contribution

1. Fork the repository
2. Create a new analyzer in `src/analyzers/`
3. Add comprehensive tests
4. Update documentation
5. Submit a pull request

## 📊 Scoring System

### Authenticity Score
- **Range**: 0.0 (definitely bot) to 1.0 (definitely human)
- **Calculation**: Weighted average of all analyzer scores
- **Confidence**: Indicates reliability of the score

### Risk Levels
- **LOW**: Bot probability < 0.4
- **MEDIUM**: Bot probability 0.4-0.6
- **HIGH**: Bot probability 0.6-0.8
- **CRITICAL**: Bot probability > 0.8
- **UNKNOWN**: Insufficient data or low confidence

### Flags
Common flags include:
- `low_username_entropy`: Suspicious username patterns
- `suspicious_follower_ratios`: Unusual following behavior
- `bulk_account_creation`: Accounts created in clusters
- `low_bio_completion`: Missing profile information
- `geographic_clustering`: Unusual location patterns

## 🔧 Advanced Usage

### Custom Weights

```python
detector = ModularBotDetector()
detector.set_analyzer_weight("statistical", 0.7)
detector.set_analyzer_weight("temporal", 0.3)
detector.normalize_weights()
```

### Performance-Based Weight Updates

```python
performance_data = {
    "statistical": {"precision": 0.9, "recall": 0.8, "f1": 0.85},
    "temporal": {"precision": 0.7, "recall": 0.6, "f1": 0.65}
}

detector.update_weights_from_performance(performance_data)
```

### Analyzer Information

```python
info = detector.get_analyzer_info()
for name, details in info.items():
    print(f"{name}: {details['version']} (weight: {details['weight']:.2f})")
```

## 🛡️ Security Considerations

### Adversarial Resistance
- Assume bot farms will study this code
- Use multiple detection methods
- Implement performance monitoring
- Regular algorithm updates

### Privacy Protection
- Hash sensitive data before sharing
- Anonymize usernames in examples
- Respect platform API terms of service

### Rate Limiting
- Instagram API has strict limits
- Implement exponential backoff
- Cache results appropriately
- Batch requests efficiently

## 📝 Data Structure

### FollowerData Fields
```python
@dataclass
class FollowerData:
    username: str
    follower_count: int
    following_count: int
    posts_count: int
    bio: Optional[str]
    profile_picture_url: Optional[str]
    is_verified: bool
    is_business: bool
    is_private: bool
    account_creation_date: Optional[datetime]
    last_post_date: Optional[datetime]
    location: Optional[str]
    external_url: Optional[str]
```

### Detection Result
```python
@dataclass
class DetectionResult:
    overall_authenticity_score: float
    overall_confidence: float
    bot_probability: float
    risk_level: str
    analyzer_results: List[AnalyzerResult]
    flags: List[str]
    metadata: Dict[str, Any]
    timestamp: datetime
```

## 🚨 Known Limitations

1. **Instagram API Restrictions**: Limited data access
2. **Evolving Bot Techniques**: Constantly adapting adversaries
3. **False Positives**: Legitimate accounts may be flagged
4. **Sample Size**: Small follower samples reduce accuracy
5. **Temporal Data**: Many accounts lack creation timestamps

## 🗺️ Roadmap

- [ ] **Network Analysis**: Follower graph analysis
- [ ] **Behavioral Patterns**: Engagement sequence analysis
- [ ] **ML Integration**: Machine learning classifiers
- [ ] **Real-time Detection**: Live monitoring capabilities
- [ ] **Platform Expansion**: Support for other social platforms
- [ ] **Visualization**: Detection result dashboards

## 📄 License

This project is open-source and available under the MIT License. See `LICENSE` file for details.

## 🤖 InfiniteVibe Integration

This framework is designed to integrate with the InfiniteVibe subnet validation system. Miners can use these tools to:

1. **Validate Their Own Followers**: Ensure their accounts aren't compromised
2. **Report Suspicious Accounts**: Flag competitors using fake followers
3. **Improve Algorithm**: Contribute new detection methods
4. **Monitor Competition**: Track follower authenticity across miners

## 🔗 Links

- **InfiniteVibe Subnet**: [Main Repository](https://github.com/Delta-Compute/infinitevibe)
- **Mining Guide**: [Mining Documentation](https://github.com/Delta-Compute/infinitevibe/blob/main/docs/mining.md)
- **Validator Guide**: [Validation Documentation](https://github.com/Delta-Compute/infinitevibe/blob/main/docs/validating.md)

---

**Built with ❤️ by the InfiniteVibe Community**

*Help us maintain the integrity of the mining reward system by contributing to this open-source project.*