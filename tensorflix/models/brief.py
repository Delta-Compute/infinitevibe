"""
Brief and Brief Submission models for the two-track mining system.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class BriefStatus(str, Enum):
    ACTIVE = "active"
    SELECTING_TOP10 = "selecting_top10"
    SELECTING_FINAL = "selecting_final"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SubmissionType(str, Enum):
    SUB_1 = "sub_1"  # First submission
    SUB_2 = "sub_2"  # Revision after top 10 selection


class ValidationStatus(str, Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


class Brief(BaseModel):
    """Creative brief submitted by users."""
    brief_id: str = Field(..., description="Unique identifier for the brief")
    user_email: str = Field(..., description="Email of the user who submitted the brief")
    title: str = Field(..., description="Brief title")
    description: str = Field(..., description="Detailed brief description")
    requirements: Optional[str] = Field(None, description="Technical requirements")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deadline_6hr: Optional[datetime] = Field(None, description="6 hour deadline for initial submissions")
    deadline_24hr: Optional[datetime] = Field(None, description="24 hour final deadline")
    status: BriefStatus = Field(default=BriefStatus.ACTIVE)
    top_10_miners: List[str] = Field(default_factory=list, description="Selected top 10 miner hotkeys")
    final_3_miners: List[str] = Field(default_factory=list, description="Final 3 selected miner hotkeys")
    
    def __init__(self, **data):
        """Initialize Brief with automatic deadline calculation."""
        super().__init__(**data)
        if self.deadline_6hr is None:
            self.deadline_6hr = self.created_at + timedelta(hours=6)
        if self.deadline_24hr is None:
            self.deadline_24hr = self.created_at + timedelta(hours=24)
    
    def is_active(self) -> bool:
        """Check if brief is still accepting submissions."""
        return (
            self.status == BriefStatus.ACTIVE and 
            datetime.utcnow() < self.deadline_24hr
        )
    
    def is_in_review_phase(self) -> bool:
        """Check if brief is in 6hr review phase."""
        return (
            datetime.utcnow() >= self.deadline_6hr and
            self.status in [BriefStatus.ACTIVE, BriefStatus.SELECTING_TOP10]
        )
    
    def can_submit_revision(self, miner_hotkey: str) -> bool:
        """Check if a miner can submit a revision."""
        return (
            miner_hotkey in self.top_10_miners and
            self.status == BriefStatus.SELECTING_TOP10
        )


class BriefSubmission(BaseModel):
    """Miner submission to a brief."""
    submission_id: str = Field(..., description="Unique submission identifier")
    brief_id: str = Field(..., description="Associated brief ID")
    miner_hotkey: str = Field(..., description="Miner's hotkey")
    submission_type: SubmissionType = Field(..., description="sub_1 or sub_2")
    r2_link: str = Field(..., description="R2 storage link to video")
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    validation_status: ValidationStatus = Field(default=ValidationStatus.PENDING)
    validation_message: Optional[str] = Field(None, description="Validation error/success message")
    gcp_streaming_url: Optional[str] = Field(None, description="GCP Media CDN streaming URL")
    
    # Scoring metrics
    submission_speed_ms: Optional[int] = Field(None, description="Time from brief creation to submission in ms")
    quality_score: Optional[float] = Field(None, description="Content quality score 0-1")
    
    def calculate_speed_score(self, brief: Brief) -> float:
        """Calculate speed score (0-30 points) based on submission time."""
        if not self.submission_speed_ms:
            time_diff = self.submitted_at - brief.created_at
            self.submission_speed_ms = int(time_diff.total_seconds() * 1000)
        
        # First hour = 30 points, linear decay to 0 at 24hrs
        hours_elapsed = self.submission_speed_ms / (1000 * 60 * 60)
        if hours_elapsed <= 1:
            return 30.0
        elif hours_elapsed >= 24:
            return 0.0
        else:
            # Linear decay from 30 to 0 over 23 hours
            return 30.0 * (1 - (hours_elapsed - 1) / 23)
    
    def calculate_selection_score(self, brief: Brief) -> float:
        """Calculate selection score based on user selections."""
        score = 0.0
        if self.miner_hotkey in brief.top_10_miners:
            score += 30.0
        if self.miner_hotkey in brief.final_3_miners:
            score += 40.0
        return score
    
    def calculate_total_score(self, brief: Brief) -> float:
        """Calculate total score for this submission."""
        if self.validation_status != ValidationStatus.VALID:
            return 0.0
        
        speed_score = self.calculate_speed_score(brief)
        selection_score = self.calculate_selection_score(brief)
        quality_multiplier = self.quality_score or 1.0
        
        return (speed_score + selection_score) * quality_multiplier


class BriefCommitMessage(BaseModel):
    """Parsed commit message for brief submissions."""
    brief_id: str
    submission_type: SubmissionType
    r2_link: str
    
    @classmethod
    def parse(cls, commit_message: str) -> Optional['BriefCommitMessage']:
        """Parse commit message format: {briefId}:sub_1:{r2_link}"""
        try:
            parts = commit_message.strip().split(':', 2)
            if len(parts) != 3:
                return None
            
            brief_id, sub_type, r2_link = parts
            
            # Validate submission type
            if sub_type not in ['sub_1', 'sub_2']:
                return None
            
            return cls(
                brief_id=brief_id,
                submission_type=SubmissionType(sub_type),
                r2_link=r2_link
            )
        except Exception:
            return None