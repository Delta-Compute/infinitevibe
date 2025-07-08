"""
Tests for the main bot detector.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from analyzers.base import FollowerData, AnalyzerResult
from detector import ModularBotDetector


class TestModularBotDetector(unittest.TestCase):
    """Test the main bot detector functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = ModularBotDetector()
        
        # Create sample follower data
        self.human_like_followers = [
            FollowerData(
                username="john_doe_123",
                follower_count=850,
                following_count=320,
                posts_count=45,
                bio="Love photography and travel 📸",
                profile_picture_url="https://example.com/pic1.jpg",
                is_verified=False,
                is_business=False,
                is_private=False,
                account_creation_date=datetime.now() - timedelta(days=365),
                last_post_date=datetime.now() - timedelta(days=5),
                location="New York, NY",
                external_url="https://johndoe.com"
            ),
            FollowerData(
                username="travel_sarah",
                follower_count=1200,
                following_count=450,
                posts_count=128,
                bio="Digital nomad | Coffee lover ☕",
                profile_picture_url="https://example.com/pic2.jpg",
                is_verified=False,
                is_business=True,
                is_private=False,
                account_creation_date=datetime.now() - timedelta(days=800),
                last_post_date=datetime.now() - timedelta(days=2),
                location="Los Angeles, CA",
                external_url=None
            )
        ]
        
        self.bot_like_followers = [
            FollowerData(
                username="user123456789",
                follower_count=5,
                following_count=2000,
                posts_count=0,
                bio="",
                profile_picture_url=None,
                is_verified=False,
                is_business=False,
                is_private=False,
                account_creation_date=datetime.now() - timedelta(days=10),
                last_post_date=None,
                location=None,
                external_url=None
            ),
            FollowerData(
                username="abc_def_456",
                follower_count=12,
                following_count=1500,
                posts_count=1,
                bio="",
                profile_picture_url=None,
                is_verified=False,
                is_business=False,
                is_private=False,
                account_creation_date=datetime.now() - timedelta(days=15),
                last_post_date=datetime.now() - timedelta(days=500),
                location=None,
                external_url=None
            )
        ]
    
    def test_detector_initialization(self):
        """Test that detector initializes with default analyzers"""
        self.assertIn("statistical", self.detector.analyzers)
        self.assertIn("temporal", self.detector.analyzers)
        self.assertEqual(len(self.detector.analyzers), 2)
    
    def test_register_analyzer(self):
        """Test registering a new analyzer"""
        mock_analyzer = Mock()
        mock_analyzer.name = "test_analyzer"
        mock_analyzer.version = "1.0.0"
        
        self.detector.register_analyzer("test", mock_analyzer, 0.3)
        
        self.assertIn("test", self.detector.analyzers)
        self.assertEqual(self.detector.weights["test"], 0.3)
    
    def test_remove_analyzer(self):
        """Test removing an analyzer"""
        self.detector.remove_analyzer("statistical")
        self.assertNotIn("statistical", self.detector.analyzers)
        self.assertNotIn("statistical", self.detector.weights)
    
    def test_analyze_human_like_followers(self):
        """Test analysis of human-like followers"""
        result = self.detector.analyze(self.human_like_followers)
        
        self.assertIsNotNone(result)
        self.assertTrue(0.0 <= result.overall_authenticity_score <= 1.0)
        self.assertTrue(0.0 <= result.bot_probability <= 1.0)
        self.assertIn(result.risk_level, ["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"])
        
        # Human-like followers should have lower bot probability
        self.assertLess(result.bot_probability, 0.7)
    
    def test_analyze_bot_like_followers(self):
        """Test analysis of bot-like followers"""
        result = self.detector.analyze(self.bot_like_followers)
        
        self.assertIsNotNone(result)
        self.assertTrue(0.0 <= result.overall_authenticity_score <= 1.0)
        self.assertTrue(0.0 <= result.bot_probability <= 1.0)
        
        # Bot-like followers should have higher bot probability
        self.assertGreater(result.bot_probability, 0.3)
    
    def test_analyze_empty_data(self):
        """Test analysis with empty data"""
        result = self.detector.analyze([])
        
        self.assertEqual(result.overall_authenticity_score, 0.5)
        self.assertEqual(result.overall_confidence, 0.0)
        self.assertEqual(result.bot_probability, 0.5)
        self.assertEqual(result.risk_level, "UNKNOWN")
        self.assertIn("no_data", result.flags)
    
    def test_analyze_single_account(self):
        """Test single account analysis"""
        result = self.detector.analyze_single_account(self.human_like_followers[0])
        
        self.assertIsNotNone(result)
        self.assertEqual(len(result.analyzer_results), 2)  # Should run both analyzers
    
    def test_get_analyzer_info(self):
        """Test getting analyzer information"""
        info = self.detector.get_analyzer_info()
        
        self.assertIn("statistical", info)
        self.assertIn("temporal", info)
        
        stat_info = info["statistical"]
        self.assertIn("name", stat_info)
        self.assertIn("version", stat_info)
        self.assertIn("weight", stat_info)
        self.assertIn("required_fields", stat_info)
    
    def test_normalize_weights(self):
        """Test weight normalization"""
        self.detector.set_analyzer_weight("statistical", 0.8)
        self.detector.set_analyzer_weight("temporal", 0.6)
        
        self.detector.normalize_weights()
        
        total_weight = sum(self.detector.weights.values())
        self.assertAlmostEqual(total_weight, 1.0, places=5)
    
    def test_update_weights_from_performance(self):
        """Test updating weights based on performance"""
        performance_data = {
            "statistical": {"precision": 0.9, "recall": 0.8, "f1": 0.85},
            "temporal": {"precision": 0.6, "recall": 0.5, "f1": 0.55}
        }
        
        original_stat_weight = self.detector.weights["statistical"]
        original_temp_weight = self.detector.weights["temporal"]
        
        self.detector.update_weights_from_performance(performance_data)
        
        # Statistical analyzer should get higher weight (good F1)
        self.assertGreater(self.detector.weights["statistical"], original_stat_weight)
        # Temporal analyzer should get lower weight (poor F1)
        self.assertLess(self.detector.weights["temporal"], original_temp_weight)
    
    def test_result_serialization(self):
        """Test result serialization to dict and JSON"""
        result = self.detector.analyze(self.human_like_followers)
        
        # Test to_dict
        result_dict = result.to_dict()
        self.assertIsInstance(result_dict, dict)
        self.assertIn("overall_authenticity_score", result_dict)
        self.assertIn("timestamp", result_dict)
        
        # Test to_json
        result_json = result.to_json()
        self.assertIsInstance(result_json, str)
        
        # Should be valid JSON
        import json
        parsed = json.loads(result_json)
        self.assertIsInstance(parsed, dict)


if __name__ == '__main__':
    unittest.main()