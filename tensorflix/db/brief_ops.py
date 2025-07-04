"""
Database operations for briefs and brief submissions.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from loguru import logger

from tensorflix.models.brief import (
    Brief, BriefSubmission, BriefStatus, SubmissionType, 
    ValidationStatus, BriefCommitMessage
)


class BriefDatabase:
    """Handles all brief-related database operations."""
    
    def __init__(self, db_client: AsyncIOMotorClient, db_name: str = "infinitevibe"):
        self.db: AsyncIOMotorDatabase = db_client[db_name]
        self.briefs_collection = self.db["briefs"]
        self.submissions_collection = self.db["brief_submissions"]
        
    async def create_indexes(self):
        """Create necessary database indexes."""
        # Brief indexes
        await self.briefs_collection.create_index("brief_id", unique=True)
        await self.briefs_collection.create_index("user_email")
        await self.briefs_collection.create_index("status")
        await self.briefs_collection.create_index("created_at")
        
        # Submission indexes
        await self.submissions_collection.create_index("submission_id", unique=True)
        await self.submissions_collection.create_index("brief_id")
        await self.submissions_collection.create_index("miner_hotkey")
        await self.submissions_collection.create_index([("brief_id", 1), ("miner_hotkey", 1)])
        await self.submissions_collection.create_index("validation_status")
        
    # ============== Brief Operations ==============
    
    async def create_brief(self, brief: Brief) -> bool:
        """Create a new brief."""
        try:
            result = await self.briefs_collection.insert_one(brief.model_dump())
            return result.inserted_id is not None
        except Exception as e:
            logger.error(f"Failed to create brief: {e}")
            return False
    
    async def get_brief(self, brief_id: str) -> Optional[Brief]:
        """Get a brief by ID."""
        doc = await self.briefs_collection.find_one({"brief_id": brief_id})
        return Brief(**doc) if doc else None
    
    async def get_active_briefs(self) -> List[Brief]:
        """Get all active briefs."""
        cursor = self.briefs_collection.find({
            "status": BriefStatus.ACTIVE,
            "deadline_24hr": {"$gt": datetime.utcnow()}
        })
        briefs = []
        async for doc in cursor:
            briefs.append(Brief(**doc))
        return briefs
    
    async def get_briefs_needing_deadline_reminder(self, hours_before: int = 2) -> List[Brief]:
        """Get briefs that need deadline reminders."""
        reminder_time = datetime.utcnow() + timedelta(hours=hours_before)
        cursor = self.briefs_collection.find({
            "status": BriefStatus.ACTIVE,
            "deadline_24hr": {
                "$gt": datetime.utcnow(),
                "$lte": reminder_time
            }
        })
        briefs = []
        async for doc in cursor:
            briefs.append(Brief(**doc))
        return briefs
    
    async def update_brief_status(self, brief_id: str, status: BriefStatus) -> bool:
        """Update brief status."""
        result = await self.briefs_collection.update_one(
            {"brief_id": brief_id},
            {"$set": {"status": status}}
        )
        return result.modified_count > 0
    
    async def set_top_10_miners(self, brief_id: str, miner_hotkeys: List[str]) -> bool:
        """Set the top 10 selected miners."""
        result = await self.briefs_collection.update_one(
            {"brief_id": brief_id},
            {
                "$set": {
                    "top_10_miners": miner_hotkeys,
                    "status": BriefStatus.SELECTING_TOP10
                }
            }
        )
        return result.modified_count > 0
    
    async def set_final_3_miners(self, brief_id: str, miner_hotkeys: List[str]) -> bool:
        """Set the final 3 selected miners."""
        result = await self.briefs_collection.update_one(
            {"brief_id": brief_id},
            {
                "$set": {
                    "final_3_miners": miner_hotkeys,
                    "status": BriefStatus.COMPLETED
                }
            }
        )
        return result.modified_count > 0
    
    # ============== Submission Operations ==============
    
    async def create_submission(self, submission: BriefSubmission) -> bool:
        """Create a new submission."""
        try:
            # Check for duplicate submission
            existing = await self.submissions_collection.find_one({
                "brief_id": submission.brief_id,
                "miner_hotkey": submission.miner_hotkey,
                "submission_type": submission.submission_type
            })
            if existing:
                logger.warning(f"Duplicate submission attempt: {submission.brief_id} - {submission.miner_hotkey}")
                return False
            
            result = await self.submissions_collection.insert_one(submission.model_dump())
            return result.inserted_id is not None
        except Exception as e:
            logger.error(f"Failed to create submission: {e}")
            return False
    
    async def get_submission(self, submission_id: str) -> Optional[BriefSubmission]:
        """Get a submission by ID."""
        doc = await self.submissions_collection.find_one({"submission_id": submission_id})
        return BriefSubmission(**doc) if doc else None
    
    async def get_brief_submissions(self, brief_id: str, 
                                   submission_type: Optional[SubmissionType] = None) -> List[BriefSubmission]:
        """Get all submissions for a brief."""
        query = {"brief_id": brief_id}
        if submission_type:
            query["submission_type"] = submission_type
            
        cursor = self.submissions_collection.find(query).sort("submitted_at", 1)
        submissions = []
        async for doc in cursor:
            submissions.append(BriefSubmission(**doc))
        return submissions
    
    async def get_miner_submissions(self, miner_hotkey: str, brief_id: str) -> List[BriefSubmission]:
        """Get all submissions by a miner for a specific brief."""
        cursor = self.submissions_collection.find({
            "miner_hotkey": miner_hotkey,
            "brief_id": brief_id
        })
        submissions = []
        async for doc in cursor:
            submissions.append(BriefSubmission(**doc))
        return submissions
    
    async def update_submission_validation(self, submission_id: str, 
                                         status: ValidationStatus, 
                                         message: Optional[str] = None) -> bool:
        """Update submission validation status."""
        update_data = {"validation_status": status}
        if message:
            update_data["validation_message"] = message
            
        result = await self.submissions_collection.update_one(
            {"submission_id": submission_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def update_submission_streaming_url(self, submission_id: str, gcp_url: str) -> bool:
        """Update submission with GCP streaming URL."""
        result = await self.submissions_collection.update_one(
            {"submission_id": submission_id},
            {"$set": {"gcp_streaming_url": gcp_url}}
        )
        return result.modified_count > 0
    
    async def get_miners_without_submissions(self, brief_id: str) -> List[str]:
        """Get list of miners who haven't submitted to a brief."""
        # This would need to cross-reference with active miners from metagraph
        # For now, return empty list - will be implemented with validator integration
        return []
    
    async def get_pending_validations(self) -> List[BriefSubmission]:
        """Get all submissions pending validation."""
        cursor = self.submissions_collection.find({
            "validation_status": ValidationStatus.PENDING
        }).sort("submitted_at", 1)
        
        submissions = []
        async for doc in cursor:
            submissions.append(BriefSubmission(**doc))
        return submissions
    
    # ============== Analytics Operations ==============
    
    async def get_brief_stats(self, brief_id: str) -> Dict[str, Any]:
        """Get statistics for a brief."""
        brief = await self.get_brief(brief_id)
        if not brief:
            return {}
        
        # Count submissions
        total_submissions = await self.submissions_collection.count_documents({
            "brief_id": brief_id
        })
        
        # Count by type
        sub1_count = await self.submissions_collection.count_documents({
            "brief_id": brief_id,
            "submission_type": SubmissionType.SUB_1
        })
        
        sub2_count = await self.submissions_collection.count_documents({
            "brief_id": brief_id,
            "submission_type": SubmissionType.SUB_2
        })
        
        # Count unique miners
        pipeline = [
            {"$match": {"brief_id": brief_id}},
            {"$group": {"_id": "$miner_hotkey"}},
            {"$count": "unique_miners"}
        ]
        result = await self.submissions_collection.aggregate(pipeline).to_list(1)
        unique_miners = result[0]["unique_miners"] if result else 0
        
        return {
            "brief_id": brief_id,
            "status": brief.status,
            "total_submissions": total_submissions,
            "first_submissions": sub1_count,
            "revisions": sub2_count,
            "unique_miners": unique_miners,
            "top_10_selected": len(brief.top_10_miners),
            "final_3_selected": len(brief.final_3_miners)
        }