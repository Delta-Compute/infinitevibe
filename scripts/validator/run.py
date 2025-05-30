import httpx
import time
import logging
import json
import asyncio
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import os

# Import the platform tracker data types
from tensorflix.services.platform_tracker.data_types import (
    YoutubeVideoMetadataRequest,
    YoutubeVideoMetadata,
    InstagramPostMetadataRequest,
    InstagramPostMetadata,
)


@dataclass
class Task:
    """Represents a validation task"""

    task_id: str
    description: str
    platform: str
    start_at: datetime

    @classmethod
    def from_dict(cls, task_id: str, data: dict) -> "Task":
        return cls(
            task_id=task_id,
            description=data["description"],
            platform=data["platform"],
            start_at=datetime.fromisoformat(data["start_at"].replace("Z", "+00:00")),
        )


@dataclass
class Submission:
    """Represents a miner submission"""

    uid: int
    task_id: str
    video_id: str
    timestamp: float

    @property
    def repr_key(self) -> str:
        """Unique representation of submission for deduplication"""
        return f"{self.task_id}:{self.video_id}"


@dataclass
class VideoMetrics:
    """Stores video/content metrics"""

    view_count: int
    like_count: int
    comment_count: int
    published_at: datetime
    last_updated: datetime

    def get_normalized_score(self, hours_since_publish: float) -> float:
        """Calculate normalized score based on views per hour"""
        if hours_since_publish <= 0:
            return 0
        return self.view_count / hours_since_publish


class VideoTopicValidator:
    def __init__(
        self,
        validator_gist_id: str,
        validator_username: str,
        platform_tracker_url: str = "http://localhost:8000",
        peer_metadata_url: str = "http://localhost:8001",
        update_interval_hours: int = 24,
        log_level: str = "INFO",
    ):
        self.validator_gist_id = validator_gist_id
        self.validator_username = validator_username
        self.validator_commit = f"{validator_username}/{validator_gist_id}"
        self.platform_tracker_url = platform_tracker_url
        self.peer_metadata_url = peer_metadata_url
        self.update_interval = timedelta(hours=update_interval_hours)

        # Storage
        self.tasks: Dict[str, Task] = {}
        self.submissions: Dict[str, List[Submission]] = defaultdict(list)
        self.metrics: Dict[Tuple[str, str], VideoMetrics] = (
            {}
        )  # (task_id, content_id) -> metrics
        self.scores: Dict[Tuple[str, int], float] = {}  # (task_id, uid) -> score

        self.setup_logging(log_level)

    def setup_logging(self, level: str):
        from loguru import logger

        self.logger = logger

    async def fetch_tasks(self) -> Dict[str, Task]:
        """Fetch current tasks from validator's gist"""
        url = f"https://gist.githubusercontent.com/{self.validator_commit}/raw/?t={time.time()}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30)
                response.raise_for_status()

            tasks = {}
            for line in response.text.strip().split("\n"):
                line = line.strip()
                if line:
                    data = json.loads(line)
                    task_id = list(data.keys())[0]
                    task_data = data[task_id]
                    tasks[task_id] = Task.from_dict(task_id, task_data)

            self.logger.info(f"Fetched {len(tasks)} tasks")
            return tasks

        except Exception as e:
            self.logger.error(f"Error fetching tasks: {e}")
            return {}

    async def fetch_miner_submissions(self) -> Dict[int, List[Dict]]:
        """Fetch all miner submissions from peer metadata"""
        url = f"{self.peer_metadata_url}/get_all_peers_metadata"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30)
                response.raise_for_status()

            data = response.json()
            miners = data.get("data", [])
            self.logger.info(f"Fetched {len(miners)} miners")

            return miners

        except Exception as e:
            self.logger.error(f"Error fetching miner metadata: {e}")
            return {}

    async def fetch_single_miner_submissions(
        self, uid: int, username: str, gist_id: str
    ) -> List[Dict]:
        """Fetch submissions from a single miner's gist"""
        url = f"https://gist.githubusercontent.com/{username}/{gist_id}/raw/?t={time.time()}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                response.raise_for_status()

            # Parse the entire gist content as a single JSON object
            data = json.loads(response.text.strip())
            submissions = []
            if "submissions" in data and isinstance(data["submissions"], list):
                for submission in data["submissions"]:
                    if isinstance(submission, list) and len(submission) == 2:
                        task_id, video_id = submission
                        submissions.append(
                            {
                                "task_id": task_id,
                                "video_id": video_id,
                                "timestamp": time.time(),  # Record when we saw it
                            }
                        )
                    else:
                        self.logger.warning(
                            f"Invalid submission format from miner {uid}: {submission}"
                        )

            self.logger.debug(f"Miner {uid} has {len(submissions)} submissions")
            return submissions

        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid JSON in miner {uid} gist: {e}")
            return []
        except Exception as e:
            self.logger.warning(f"Error fetching submissions for miner {uid}: {e}")
            return []

    async def fetch_content_metrics(
        self, task_id: str, video_id: str, platform: str
    ) -> Optional[VideoMetrics]:
        """Fetch metrics for a specific content piece"""
        try:
            if platform == "youtube":
                url = f"{self.platform_tracker_url}/youtube/video/{video_id}"
            elif platform == "instagram":
                url = f"{self.platform_tracker_url}/instagram/reel/{video_id}"
            else:
                self.logger.error(f"Unknown platform: {platform}")
                return None

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30)
                response.raise_for_status()

            data = response.json()

            # published_at can be 

            return VideoMetrics(
                view_count=data.get("view_count", 0),
                like_count=data.get("like_count", 0),
                comment_count=data.get("comment_count", 0),
                published_at=datetime.fromisoformat(
                    data["published_at"].replace("Z", "+00:00")
                ),
                last_updated=datetime.now(),
            )

        except Exception as e:
            self.logger.error(f"Error fetching metrics for {video_id}: {e}")
            return None

    def validate_submission_uniqueness(
        self, submissions: List[Submission], task_id: str
    ) -> Dict[int, bool]:
        """Check for duplicate submissions"""
        validity = {}
        seen = {}

        # Sort by timestamp to prioritize earlier submissions
        sorted_submissions = sorted(submissions, key=lambda s: s.timestamp)

        for sub in sorted_submissions:
            if sub.repr_key in seen:
                validity[sub.uid] = False
                self.logger.info(
                    f"Duplicate submission from uid {sub.uid} for {sub.repr_key}"
                )
            else:
                seen[sub.repr_key] = sub.uid
                validity[sub.uid] = True

        return validity

    def validate_submission_timestamp(
        self, submissions: List[Submission], task: Task
    ) -> Dict[int, bool]:
        """Validate that content was published after task start time"""
        validity = {}
        start_timestamp = task.start_at.timestamp()

        for sub in submissions:
            # Get metrics to check published time
            metrics_key = (sub.task_id, sub.video_id)
            if metrics_key in self.metrics:
                metrics = self.metrics[metrics_key]
                published_timestamp = metrics.published_at.timestamp()

                if published_timestamp >= start_timestamp:
                    validity[sub.uid] = True
                else:
                    validity[sub.uid] = False
                    self.logger.info(
                        f"Content {sub.video_id} from uid {sub.uid} "
                        f"published before task start"
                    )
            else:
                # If we don't have metrics, we can't validate
                validity[sub.uid] = False

        return validity

    def calculate_scores(self, task_id: str) -> Dict[int, float]:
        """Calculate normalized scores for all valid submissions"""
        task = self.tasks.get(task_id)
        if not task:
            return {}

        task_submissions = self.submissions.get(task_id, [])
        if not task_submissions:
            return {}

        # Validate submissions
        uniqueness_validity = self.validate_submission_uniqueness(
            task_submissions, task_id
        )
        timestamp_validity = self.validate_submission_timestamp(task_submissions, task)

        # Calculate scores for valid submissions
        scores = {}
        for sub in task_submissions:
            # Check if submission is valid
            if not uniqueness_validity.get(sub.uid, False):
                continue
            if not timestamp_validity.get(sub.uid, False):
                continue

            # Get metrics
            metrics_key = (sub.task_id, sub.video_id)
            metrics = self.metrics.get(metrics_key)
            if not metrics:
                continue

            # Calculate hours since publish
            hours_since_publish = (
                datetime.now() - metrics.published_at
            ).total_seconds() / 3600

            # Get normalized score
            score = metrics.get_normalized_score(hours_since_publish)
            scores[sub.uid] = score

        # Normalize scores to 0-1 range
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {uid: score / max_score for uid, score in scores.items()}

        return scores

    async def update_cycle(self):
        """Run one update cycle"""
        self.logger.info("Starting update cycle")

        # Fetch latest tasks
        self.tasks = await self.fetch_tasks()

        # Fetch all miner submissions
        miner_submissions = await self.fetch_miner_submissions()

        # Process submissions
        self.submissions.clear()
        for miner in miner_submissions:
            uid = miner.get("uid")
            submissions = miner.get("submissions")
            for sub_data in submissions:
                submission = Submission(
                    uid=uid,
                    task_id=sub_data["task_id"],
                    video_id=sub_data["video_id"],
                    timestamp=sub_data.get("timestamp", time.time()),
                )

                # Only process if task exists
                if submission.task_id in self.tasks:
                    self.submissions[submission.task_id].append(submission)

        # Update metrics for all submissions
        for task_id, task in self.tasks.items():
            task_submissions = self.submissions.get(task_id, [])

            for sub in task_submissions:
                metrics_key = (sub.task_id, sub.video_id)

                # Check if we need to update metrics
                if metrics_key in self.metrics:
                    last_update = self.metrics[metrics_key].last_updated
                    if datetime.now() - last_update < timedelta(hours=1):
                        continue

                # Fetch updated metrics
                metrics = await self.fetch_content_metrics(
                    sub.task_id, sub.video_id, task.platform
                )
                if metrics:
                    self.metrics[metrics_key] = metrics

        # Calculate scores for each task
        self.scores.clear()
        for task_id in self.tasks:
            task_scores = self.calculate_scores(task_id)
            for uid, score in task_scores.items():
                self.scores[(task_id, uid)] = score

        # Log summary
        self.logger.info(f"Update cycle complete:")
        self.logger.info(f"  - Tasks: {len(self.tasks)}")
        self.logger.info(
            f"  - Total submissions: {sum(len(s) for s in self.submissions.values())}"
        )
        self.logger.info(f"  - Metrics cached: {len(self.metrics)}")
        self.logger.info(f"  - Scores calculated: {len(self.scores)}")

        # Log top performers per task
        for task_id, task in self.tasks.items():
            task_scores = {
                uid: score
                for (tid, uid), score in self.scores.items()
                if tid == task_id
            }
            if task_scores:
                top_performers = sorted(
                    task_scores.items(), key=lambda x: x[1], reverse=True
                )[:5]
                self.logger.info(f"Top performers for task {task_id}:")
                for uid, score in top_performers:
                    self.logger.info(f"  - UID {uid}: {score:.4f}")

    async def run(self):
        """Main validation loop"""
        self.logger.info("Starting video topic validator")
        self.logger.info(f"Validator commit: {self.validator_commit}")
        self.logger.info(f"Update interval: {self.update_interval}")

        while True:
            try:
                await self.update_cycle()

                # Sleep until next update
                sleep_seconds = self.update_interval.total_seconds()
                self.logger.info(f"Sleeping for {sleep_seconds} seconds")
                await asyncio.sleep(sleep_seconds)

            except KeyboardInterrupt:
                self.logger.info("Validator stopped by user")
                break
            except Exception as e:
                self.logger.error(
                    f"Error in validation loop: {e}", exc_info=True, stack_info=True
                )
                # Sleep a bit before retrying
                await asyncio.sleep(60)


async def main():
    """Main entry point"""
    validator = VideoTopicValidator(
        validator_gist_id="cdc3b8166f8f6bc5dd8f70fd84d343c7",
        validator_username="toilaluan",
        platform_tracker_url="http://localhost:8000",
        peer_metadata_url="http://localhost:8001",
        update_interval_hours=24,  # Update daily
        log_level="INFO",
    )

    await validator.run()


if __name__ == "__main__":
    asyncio.run(main())
