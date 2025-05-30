from loguru import logger


def validating_submission_uniqueness(
    repr_submissions: list[str], timestamps: list[float], uids: list[int], task_id: str
) -> list[bool]:
    logger.info(f"Validating submission for task {task_id}")
    logger.info(f"Repr submissions: {repr_submissions}")
    logger.info(f"Uids: {uids}")

    is_valid = [True] * len(uids)

    # Group into duplicated submissions
    groups = {}
    for submission, uid, timestamp in zip(repr_submissions, uids, timestamps):
        groups.setdefault(submission.strip(), []).append((uid, timestamp))

    # Check if the submission is valid.
    for submission, uids_timestamps in groups.items():
        uids_timestamps.sort(key=lambda x: x[1])
        for uid, _ in uids_timestamps[1:]:
            is_valid[uid] = False

    return is_valid


def validating_submission_timestamp(
    timestamps: list[float], uids: list[int], task_id: str, start_timestamp: float
) -> list[bool]:
    """
    Submission is valid if the timestamp after the start timestamp.
    """
    logger.info(f"Validating submission for task {task_id}")
    logger.info(f"Timestamps: {timestamps}")
    logger.info(f"Uids: {uids}")

    is_valid = [True] * len(uids)

    for timestamp, uid in zip(timestamps, uids):
        if timestamp >= start_timestamp:
            is_valid[uid] = False

    return is_valid

