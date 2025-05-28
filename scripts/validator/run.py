import httpx
import time
import logging
from typing import Dict, List, Set
from tqdm import tqdm
import json


class TaskProcessor:
    def __init__(self, validator_commit: str, sleep_interval: int = 10):
        self.validator_commit = validator_commit
        self.sleep_interval = sleep_interval
        self.processed_tasks: Set[str] = set()
        self.setup_logging()

    def setup_logging(self):
        """Configure logging with both file and console output"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("task_processor.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def fetch_task_data(self) -> Dict:
        """Fetch task data from GitHub gist"""
        url = f"https://gist.githubusercontent.com/{self.validator_commit}/raw"
        try:
            self.logger.info(f"Fetching task data from: {url}")
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            self.logger.info(f"Successfully fetched {len(data)} tasks")
            return data
        except httpx.RequestError as e:
            self.logger.error(f"Network error fetching task data: {e}")
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Unexpected error fetching task data: {e}")
            return {}

    def fetch_miner_metadata(self) -> List[Dict]:
        """Fetch miner commits metadata"""
        url = "http://localhost:8001/get_all_peers_metadata"
        try:
            self.logger.info("Fetching miner metadata...")
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            miners = data.get("data", [])
            self.logger.info(f"Found {len(miners)} miners")
            return miners
        except httpx.RequestError as e:
            self.logger.error(f"Network error fetching miner metadata: {e}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error in miner metadata: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching miner metadata: {e}")
            return []

    def fetch_video_data(self, video_id: str) -> Dict:
        """Fetch video data from platform API"""
        url = f"http://localhost:8000/youtube/video/{video_id}"
        try:
            self.logger.debug(f"Fetching video data for ID: {video_id}")
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            self.logger.debug(f"Successfully fetched video data for {video_id}")
            return data
        except httpx.RequestError as e:
            self.logger.warning(f"Network error fetching video {video_id}: {e}")
            return {}
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON decode error for video {video_id}: {e}")
            return {}
        except Exception as e:
            self.logger.warning(f"Unexpected error fetching video {video_id}: {e}")
            return {}

    def process_task_submissions(
        self, task_id: str, task_data: Dict, miners: List[Dict]
    ):
        """Process submissions for a specific task"""

        # Progress bar for processing miners
        with tqdm(
            total=len(miners),
            desc=f"Processing miners for task {task_id}",
            unit="miner",
            leave=False,
        ) as miner_pbar:

            for miner in miners:
                submissions = miner.get("submissions", [])
                if not submissions:
                    self.logger.info(f"No submissions found for task {task_id}")
                    self.logger.info(f"Task data: {task_data}")
                    return

                miner_uid = miner.get("uid", "unknown")
                miner_pbar.set_description(f"Checking miner {miner_uid}")

                # Check if this miner has submissions for this task
                miner_submissions = [
                    s for s in submissions if s.get("task_id") == task_id
                ]

                if miner_submissions:
                    self.logger.info(
                        f"Miner {miner_uid} has {len(miner_submissions)} submission(s) for task {task_id}"
                    )

                    # Process each submission with progress tracking
                    with tqdm(
                        total=len(miner_submissions),
                        desc=f"Processing submissions from miner {miner_uid}",
                        unit="submission",
                        leave=False,
                    ) as sub_pbar:

                        for submission in miner_submissions:
                            video_id = submission.get("video_id")
                            if video_id:
                                self.logger.info(
                                    f"Processing video {video_id} from miner {miner_uid}"
                                )
                                video_data = self.fetch_video_data(video_id)

                                if video_data:
                                    self.logger.info(
                                        f"Video data retrieved: {json.dumps(video_data, indent=2)}"
                                    )
                                else:
                                    self.logger.warning(
                                        f"Failed to retrieve video data for {video_id}"
                                    )
                            else:
                                self.logger.warning(
                                    f"No video_id found in submission from miner {miner_uid}"
                                )

                            sub_pbar.update(1)
                            time.sleep(0.1)  # Small delay to avoid overwhelming APIs

                miner_pbar.update(1)

    def process_new_tasks(self, all_tasks: Dict):
        """Process only new tasks that haven't been processed yet"""
        new_tasks = {
            task_id: task_data
            for task_id, task_data in all_tasks.items()
            if task_id not in self.processed_tasks
        }

        if not new_tasks:
            self.logger.info("No new tasks to process")
            return

        self.logger.info(f"Found {len(new_tasks)} new tasks to process")

        # Fetch miner metadata once per cycle
        miners = self.fetch_miner_metadata()
        if not miners:
            self.logger.warning("No miners found, skipping task processing")
            return
        else:
            self.logger.info(f"Found {len(miners)} miners")
            self.logger.info(f"Miners: {miners}")

        # Progress bar for processing tasks
        with tqdm(
            total=len(new_tasks), desc="Processing new tasks", unit="task"
        ) as task_pbar:
            for task_id, task_data in new_tasks.items():
                task_pbar.set_description(f"Processing task {task_id}")
                self.logger.info(f"Processing task: {task_id}")
                self.logger.debug(f"Task data: {json.dumps(task_data, indent=2)}")

                # Process submissions for this task
                self.process_task_submissions(task_id, task_data, miners)

                # Mark task as processed
                self.processed_tasks.add(task_id)
                self.logger.info(f"Task {task_id} marked as processed")

                task_pbar.update(1)

                # Break after first task (matching original behavior)
                # Remove this break if you want to process all new tasks
                break

    def run(self):
        """Main processing loop"""
        self.logger.info("Starting task processor...")
        self.logger.info(f"Validator commit: {self.validator_commit}")
        self.logger.info(f"Sleep interval: {self.sleep_interval} seconds")

        cycle_count = 0

        try:
            while True:
                cycle_count += 1
                self.logger.info(f"=== Processing cycle {cycle_count} ===")
                self.logger.info(
                    f"Total processed tasks so far: {len(self.processed_tasks)}"
                )

                # Fetch all task data
                all_tasks = self.fetch_task_data()

                if all_tasks:
                    # Process new tasks
                    self.process_new_tasks(all_tasks)
                else:
                    self.logger.warning(
                        "No task data available, retrying in next cycle"
                    )

                self.logger.info(
                    f"Cycle {cycle_count} completed. Sleeping for {self.sleep_interval} seconds..."
                )
                time.sleep(self.sleep_interval)

        except KeyboardInterrupt:
            self.logger.info("Task processor stopped by user")
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}", exc_info=True)


def main():
    """Main entry point"""
    dummy_validator_commit = "toilaluan/cdc3b8166f8f6bc5dd8f70fd84d343c7"

    processor = TaskProcessor(
        validator_commit=dummy_validator_commit, sleep_interval=10
    )

    processor.run()


if __name__ == "__main__":
    main()
