"""
ID generation utilities for briefs and submissions.
"""
import uuid
from datetime import datetime


def generate_brief_id() -> str:
    """Generate a unique brief ID."""
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    unique_id = str(uuid.uuid4())[:8]
    return f"brief_{timestamp}_{unique_id}"


def generate_submission_id(brief_id: str, miner_hotkey: str, submission_type: str) -> str:
    """Generate a unique submission ID."""
    hotkey_short = miner_hotkey[-8:]
    unique_id = str(uuid.uuid4())[:8]
    return f"{brief_id}_{hotkey_short}_{submission_type}_{unique_id}"