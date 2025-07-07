"""
Main bot detector class that combines multiple analyzers.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Type
from dataclasses import dataclass, asdict
from datetime import datetime

from analyzers.base import BaseAnalyzer, FollowerData, AnalyzerResult
from analyzers.statistical import StatisticalAnalyzer
from analyzers.temporal import TemporalAnalyzer


@dataclass
class DetectionResult:
    """Final detection result combining all analyzers"""
    overall_authenticity_score: float
    overall_confidence: float
    bot_probability: float
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    analyzer_results: List[AnalyzerResult]
    flags: List[str]
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class ModularBotDetector:
    """Main bot detection system that combines multiple analyzers"""
    
    def __init__(self):
        self.analyzers: Dict[str, BaseAnalyzer] = {}
        self.weights: Dict[str, float] = {}
        self.logger = logging.getLogger(__name__)
        
        # Register default analyzers
        self.register_analyzer("statistical", StatisticalAnalyzer(), 0.5)
        self.register_analyzer("temporal", TemporalAnalyzer(), 0.5)
        
    def register_analyzer(self, name: str, analyzer: BaseAnalyzer, weight: float = 0.1) -> None:
        """
        Register a new analyzer with the detector.
        
        Args:
            name: Unique name for the analyzer
            analyzer: Analyzer instance
            weight: Weight for combining results (0.0 to 1.0)
        """
        if not isinstance(analyzer, BaseAnalyzer):
            raise ValueError("Analyzer must inherit from BaseAnalyzer")
        
        if not 0.0 <= weight <= 1.0:
            raise ValueError("Weight must be between 0.0 and 1.0")
        
        self.analyzers[name] = analyzer
        self.weights[name] = weight
        self.logger.info(f"Registered analyzer: {name} with weight {weight}")
    
    def remove_analyzer(self, name: str) -> None:
        """Remove an analyzer"""
        if name in self.analyzers:
            del self.analyzers[name]
            del self.weights[name]
            self.logger.info(f"Removed analyzer: {name}")
    
    def set_analyzer_weight(self, name: str, weight: float) -> None:
        """Update analyzer weight"""
        if name not in self.analyzers:
            raise ValueError(f"Analyzer '{name}' not found")
        
        if not 0.0 <= weight <= 1.0:
            raise ValueError("Weight must be between 0.0 and 1.0")
        
        self.weights[name] = weight
        self.logger.info(f"Updated weight for {name}: {weight}")
    
    def analyze(self, followers_data: List[FollowerData]) -> DetectionResult:
        """
        Analyze follower data using all registered analyzers.
        
        Args:
            followers_data: List of follower information
            
        Returns:
            DetectionResult with combined analysis
        """
        if not followers_data:
            return DetectionResult(
                overall_authenticity_score=0.5,
                overall_confidence=0.0,
                bot_probability=0.5,
                risk_level="UNKNOWN",
                analyzer_results=[],
                flags=["no_data"],
                metadata={"error": "No follower data provided"},
                timestamp=datetime.now()
            )
        
        # Run all analyzers
        analyzer_results = []
        total_weight = 0.0
        weighted_score = 0.0
        weighted_confidence = 0.0
        all_flags = set()
        
        for name, analyzer in self.analyzers.items():
            try:
                if analyzer.can_analyze(followers_data):
                    result = analyzer.analyze(followers_data)
                    analyzer_results.append(result)
                    
                    weight = self.weights[name]
                    total_weight += weight
                    weighted_score += result.authenticity_score * weight
                    weighted_confidence += result.confidence * weight
                    all_flags.update(result.flags)
                    
                    self.logger.debug(f"Analyzer {name}: score={result.authenticity_score:.3f}, confidence={result.confidence:.3f}")
                else:
                    self.logger.warning(f"Analyzer {name} cannot process the provided data")
            except Exception as e:
                self.logger.error(f"Analyzer {name} failed: {e}")
                # Create error result
                error_result = AnalyzerResult(
                    analyzer_name=name,
                    authenticity_score=0.5,
                    confidence=0.0,
                    details={"error": str(e)},
                    flags=["analyzer_error"]
                )
                analyzer_results.append(error_result)
                all_flags.add("analyzer_error")
        
        # Calculate final scores
        if total_weight > 0:
            overall_authenticity_score = weighted_score / total_weight
            overall_confidence = weighted_confidence / total_weight
        else:
            overall_authenticity_score = 0.5
            overall_confidence = 0.0
            all_flags.add("no_analyzers_ran")
        
        # Calculate bot probability (inverse of authenticity)
        bot_probability = 1.0 - overall_authenticity_score
        
        # Determine risk level
        risk_level = self._calculate_risk_level(bot_probability, overall_confidence)
        
        # Create metadata
        metadata = {
            "total_followers_analyzed": len(followers_data),
            "analyzers_used": len(analyzer_results),
            "total_weight": total_weight,
            "analysis_version": "1.0.0"
        }
        
        return DetectionResult(
            overall_authenticity_score=overall_authenticity_score,
            overall_confidence=overall_confidence,
            bot_probability=bot_probability,
            risk_level=risk_level,
            analyzer_results=analyzer_results,
            flags=list(all_flags),
            metadata=metadata,
            timestamp=datetime.now()
        )
    
    def _calculate_risk_level(self, bot_probability: float, confidence: float) -> str:
        """Calculate risk level based on bot probability and confidence"""
        if confidence < 0.3:
            return "UNKNOWN"
        
        if bot_probability >= 0.8:
            return "CRITICAL"
        elif bot_probability >= 0.6:
            return "HIGH"
        elif bot_probability >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"
    
    def analyze_single_account(self, account_data: FollowerData) -> DetectionResult:
        """Analyze a single account"""
        return self.analyze([account_data])
    
    def get_analyzer_info(self) -> Dict[str, Any]:
        """Get information about registered analyzers"""
        info = {}
        for name, analyzer in self.analyzers.items():
            info[name] = {
                "name": analyzer.name,
                "version": analyzer.version,
                "enabled": analyzer.enabled,
                "weight": self.weights[name],
                "required_fields": analyzer.get_required_fields()
            }
        return info
    
    def normalize_weights(self) -> None:
        """Normalize all weights to sum to 1.0"""
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            for name in self.weights:
                self.weights[name] /= total_weight
        self.logger.info("Normalized analyzer weights")
    
    def update_weights_from_performance(self, performance_data: Dict[str, Dict[str, float]]) -> None:
        """
        Update analyzer weights based on performance metrics.
        
        Args:
            performance_data: Dict of analyzer_name -> {"precision": float, "recall": float, "f1": float}
        """
        for analyzer_name, metrics in performance_data.items():
            if analyzer_name in self.weights:
                # Simple weight adjustment based on F1 score
                f1_score = metrics.get("f1", 0.5)
                
                if f1_score > 0.8:
                    self.weights[analyzer_name] *= 1.1
                elif f1_score < 0.6:
                    self.weights[analyzer_name] *= 0.9
                
                # Ensure weight stays in bounds
                self.weights[analyzer_name] = max(0.1, min(1.0, self.weights[analyzer_name]))
        
        self.normalize_weights()
        self.logger.info("Updated weights based on performance data")