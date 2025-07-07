"""
Base analyzer class for follower authenticity detection.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FollowerData:
    """Standard data structure for follower information"""
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
    
    @property
    def follower_following_ratio(self) -> float:
        """Calculate follower to following ratio"""
        if self.following_count == 0:
            return float('inf') if self.follower_count > 0 else 0
        return self.follower_count / self.following_count
    
    @property
    def has_complete_profile(self) -> bool:
        """Check if profile appears complete"""
        return bool(
            self.bio and 
            self.profile_picture_url and 
            self.posts_count > 0
        )


@dataclass
class AnalyzerResult:
    """Result from an analyzer"""
    analyzer_name: str
    authenticity_score: float  # 0.0 (definitely bot) to 1.0 (definitely human)
    confidence: float  # 0.0 (low confidence) to 1.0 (high confidence)
    details: Dict[str, Any]
    flags: List[str]  # List of suspicious behaviors detected
    
    def __post_init__(self):
        """Validate result values"""
        if not 0.0 <= self.authenticity_score <= 1.0:
            raise ValueError(f"authenticity_score must be between 0.0 and 1.0, got {self.authenticity_score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")


class BaseAnalyzer(ABC):
    """Abstract base class for all follower analyzers"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.enabled = True
        
    @abstractmethod
    def analyze(self, followers_data: List[FollowerData]) -> AnalyzerResult:
        """
        Analyze follower data and return authenticity assessment.
        
        Args:
            followers_data: List of follower information
            
        Returns:
            AnalyzerResult with authenticity score and details
        """
        pass
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """
        Return list of required fields from FollowerData.
        
        Returns:
            List of field names this analyzer needs
        """
        pass
    
    def validate_input(self, followers_data: List[FollowerData]) -> bool:
        """
        Validate that input data contains required fields.
        
        Args:
            followers_data: Data to validate
            
        Returns:
            True if data is valid for this analyzer
        """
        if not followers_data:
            return False
            
        required_fields = self.get_required_fields()
        for follower in followers_data:
            for field in required_fields:
                if not hasattr(follower, field) or getattr(follower, field) is None:
                    return False
        return True
    
    def can_analyze(self, followers_data: List[FollowerData]) -> bool:
        """
        Check if this analyzer can process the given data.
        
        Args:
            followers_data: Data to check
            
        Returns:
            True if analyzer can process this data
        """
        return self.enabled and self.validate_input(followers_data)
    
    def __str__(self) -> str:
        return f"{self.name} v{self.version}"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', version='{self.version}')>"