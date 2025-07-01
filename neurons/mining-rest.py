# mining-rest.py
from __future__ import annotations

import os
import json
import uuid
import logging
from enum import Enum
from uuid import uuid4
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict
import io

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError, EndpointConnectionError

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    Query,
)
from fastapi.responses import JSONResponse
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi import Path as FastAPIPath

from pydantic import BaseModel, Field


# ───── Setup ─────────────────────────────────────────────────────────────
logger = logging.getLogger("uvicorn.error")
SUBMISSION_LOG_FILE = Path("submissions.jsonl")


class SubmissionStatus(str, Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Platform(str, Enum):
    youtube = "youtube/video"
    instagraReel = "instagram/reel"
    instagramPost = "instagram/post"
    Tiktok = "tiktok"
    twitter = "twitter"


# ───────────────────── Models ──────────────────────


class SubmissionModel(BaseModel):
    id: str
    content_id: str
    platform: str
    status: str = Field(default="completed")
    created_at: str
    file_name: Optional[str] = None  # object key within the R2 bucket
    hotkey: Optional[str] = None  # creator hotkey
    social_post_url: Optional[str] = None  # social media post URL


class GistConfig(BaseModel):
    gist_id: str
    file_name: str
    api_key: str | None = None  # allow public gists


class R2Config(BaseModel):
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    account_id: str
    public_link_id: str


# ───────────────── In-memory "storage" ─────────────────
GIST_CFG: GistConfig | None = None
R2_CFG: R2Config | None = None

# ───────────────── FastAPI app ───────────────────────
app = FastAPI(title="Video Submission API (stateless demo)", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # loosen in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────── Helpers & probes ────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def probe_gist(cfg: GistConfig | None) -> Tuple[bool, str]:
    if cfg is None:
        return False, "not configured"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if cfg.api_key:
        headers["Authorization"] = f"token {cfg.api_key}"

    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.get(
            f"https://api.github.com/gists/{cfg.gist_id}", headers=headers
        )

    if r.status_code == 200 and cfg.file_name in r.json().get("files", {}):
        return True, "ok"
    if r.status_code == 401:
        return False, "unauthorised"
    if r.status_code == 404:
        return False, "gist/file not found"
    return False, f"github error {r.status_code}"


def probe_r2(cfg: R2Config | None) -> Tuple[bool, str]:
    if cfg is None:
        return False, "not configured"

    endpoint = f"https://{cfg.account_id}.r2.cloudflarestorage.com"
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
    )
    try:
        s3.head_bucket(Bucket=cfg.bucket_name)
        return True, "ok"
    except EndpointConnectionError:
        return False, "endpoint unreachable"
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in {"403", "AccessDenied"}:
            return False, "unauthorised"
        if code in {"404", "NoSuchBucket"}:
            return False, "bucket not found"
        return False, f"r2 error {code}"


async def require_storage_ready() -> None:
    gist_ok, _ = await probe_gist(GIST_CFG)
    r2_ok, _ = probe_r2(R2_CFG)
    if not (gist_ok and r2_ok):
        raise HTTPException(
            status_code=503,
            detail="Storage back-ends unavailable — see /health",
        )


def _r2_client():
    if R2_CFG is None:
        raise RuntimeError("R2 not configured")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_CFG.account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_CFG.access_key_id,
        aws_secret_access_key=R2_CFG.secret_access_key,
    )


# ─────────────────── Endpoints ───────────────────────

# ── HEALTH ───────────────────────────────────────────


@app.get("/health", tags=["Health"])
async def health():
    gist_ok, gist_msg = await probe_gist(GIST_CFG)
    r2_ok, r2_msg = probe_r2(R2_CFG)
    return {
        "status": "healthy" if gist_ok and r2_ok else "degraded",
        "gist": {"ok": gist_ok, "detail": gist_msg},
        "r2": {"ok": r2_ok, "detail": r2_msg},
    }


# ── STORAGE CONFIG ───────────────────────────────────


@app.post("/git", status_code=200, tags=["Storage"])
async def cfg_gist(cfg: GistConfig = Body(...)):
    ok, msg = await probe_gist(cfg)
    if not ok:
        raise HTTPException(status_code=401, detail=f"Gist check failed: {msg}")

    global GIST_CFG
    GIST_CFG = cfg
    return {"status": "ok", "message": "Gist verified 🚀"}


@app.post("/r2", status_code=200, tags=["Storage"])
def cfg_r2(cfg: R2Config):
    ok, msg = probe_r2(cfg)
    if not ok:
        raise HTTPException(status_code=401, detail=f"R2 check failed: {msg}")

    global R2_CFG
    R2_CFG = cfg
    return {"status": "ok", "message": "R2 bucket verified ✅"}


# ── SUBMISSIONS ──────────────────────────────────────


@app.get(
    "/submissions",
    response_model=List[SubmissionModel],
    tags=["Submissions"],
)
def list_submissions():
    if not R2_CFG:
        return []
    s3 = _r2_client()
    response = s3.list_objects_v2(Bucket=R2_CFG.bucket_name, Prefix="metadata/")
    submissions = []

    print(response)
    for obj in response.get("Contents", []):
        if obj["Key"].endswith(".json"):
            file_obj = s3.get_object(Bucket=R2_CFG.bucket_name, Key=obj["Key"])
            data = json.loads(file_obj["Body"].read().decode("utf-8"))
            submissions.append(SubmissionModel(**data))
    return submissions


def save_submission_to_disk(submission: SubmissionModel):
    SUBMISSION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SUBMISSION_LOG_FILE.open("a") as f:
        f.write(json.dumps(submission.dict()) + "\n")

    # Also save to Gist if configured
    if GIST_CFG:
        try:
            # Read existing content from gist
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if GIST_CFG.api_key:
                headers["Authorization"] = f"token {GIST_CFG.api_key}"

            async def update_gist():
                async with httpx.AsyncClient(timeout=8) as client:
                    # Get current gist content
                    r = await client.get(
                        f"https://api.github.com/gists/{GIST_CFG.gist_id}",
                        headers=headers,
                    )
                    if r.status_code == 200:
                        gist_data = r.json()
                        files = gist_data.get("files", {})
                        current_file = files.get(GIST_CFG.file_name, {})
                        current_content = current_file.get("content", "")

                        # Append new submission
                        new_content = (
                            current_content + json.dumps(submission.dict()) + "\n"
                        )

                        # Update gist
                        update_data = {
                            "files": {GIST_CFG.file_name: {"content": new_content}}
                        }

                        await client.patch(
                            f"https://api.github.com/gists/{GIST_CFG.gist_id}",
                            headers=headers,
                            json=update_data,
                        )

            # Run gist update in background
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                loop.create_task(update_gist())
            except RuntimeError:
                # If no event loop, create a new one
                asyncio.run(update_gist())

        except Exception as e:
            logger.exception("Failed to update gist: %s", e)


# ───── Upload Logic ───────────────────────────────────────────────────────


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def upload_multipart_to_r2(file_like, key):
    s3 = _r2_client()
    config = TransferConfig(
        multipart_threshold=8 * 1024 * 1024,
        multipart_chunksize=8 * 1024 * 1024,
        max_concurrency=5,
        use_threads=True,
    )
    file_like.seek(0)
    s3.upload_fileobj(file_like, R2_CFG.bucket_name, key, Config=config)


def background_upload(submission: SubmissionModel, file_like, key: str):
    try:
        upload_multipart_to_r2(file_like, key)
        submission.status = SubmissionStatus.completed
        submission.file_name = key

        # Also store submission metadata in R2 as JSON
        if R2_CFG:
            try:
                metadata = submission.dict()
                metadata["video_url"] = (
                    f"https://{R2_CFG.public_link_id}.r2.cloudflarestorage.com/{key}"
                )

                metadata_key = f"metadata/{submission.id}.json"
                metadata_bytes = json.dumps(metadata, indent=2).encode("utf-8")
                metadata_file = io.BytesIO(metadata_bytes)

                s3 = _r2_client()
                s3.upload_fileobj(metadata_file, R2_CFG.bucket_name, metadata_key)
                metadata_file.close()

            except Exception as e:
                logger.exception("Failed to store metadata in R2 for %s", submission.id)

    except Exception as e:
        logger.exception("Upload failed for %s", submission.id)
        submission.status = SubmissionStatus.failed
    finally:
        file_like.close()
        save_submission_to_disk(submission)


# ───── API Endpoint ───────────────────────────────────────────────────────


@app.get(
    "/submissions/{submission_id}",
    response_model=SubmissionModel,
    tags=["Submissions"],
)
def get_submission(submission_id: str):
    if not R2_CFG:
        raise HTTPException(status_code=503, detail="R2 not configured")

    s3 = _r2_client()
    try:
        metadata_key = f"metadata/{submission_id}.json"
        file_obj = s3.get_object(Bucket=R2_CFG.bucket_name, Key=metadata_key)
        data = json.loads(file_obj["Body"].read().decode("utf-8"))
        return SubmissionModel(**data)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            raise HTTPException(status_code=404, detail="Submission not found")
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve submission")


@app.delete(
    "/submissions/{submission_id}",
    status_code=204,
    tags=["Submissions"],
)
def delete_submission(submission_id: str):
    if not R2_CFG:
        raise HTTPException(status_code=503, detail="R2 not configured")

    s3 = _r2_client()

    # Delete metadata
    try:
        metadata_key = f"metadata/{submission_id}.json"
        s3.delete_object(Bucket=R2_CFG.bucket_name, Key=metadata_key)
    except ClientError as e:
        logger.error(f"Could not delete metadata for {submission_id}: {e}")
        raise HTTPException(status_code=404, detail="Submission not found")

    # best-effort delete video from R2
    try:
        prefix = f"videos/{submission_id}"
        resp = s3.list_objects_v2(Bucket=R2_CFG.bucket_name, Prefix=prefix)
        for obj in resp.get("Contents", []):
            s3.delete_object(Bucket=R2_CFG.bucket_name, Key=obj["Key"])
    except Exception:  # noqa: BLE001
        pass  # ignore – deletion is optional


@app.get(
    "/submissions/{submission_id}/download",
    tags=["Submissions"],
)
def download_submission(submission_id: str):
    sub = get_submission(submission_id)
    if not sub.file_name:
        raise HTTPException(
            status_code=404, detail="File not available for this submission"
        )
    s3 = _r2_client()
    try:
        file_obj = s3.get_object(Bucket=R2_CFG.bucket_name, Key=sub.file_name)
        return StreamingResponse(
            file_obj["Body"],
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={Path(sub.file_name).name}"
            },
        )
    except Exception as e:
        logger.exception("Failed to download file for %s", submission_id)
        raise HTTPException(status_code=500, detail="Failed to download file")


# ───── New Submission Endpoint ─────────────────────────────────────────────
@app.post("/submissions/video-upload", status_code=201, response_model=SubmissionModel)
async def submit(
    background_tasks: BackgroundTasks,
    content_id: str = Form(...),
    platform: Platform = Form(...),
    video_file: UploadFile = File(...),
    hotkey: str = Form(...),
    social_post_url: str = Form(...),
):
    sub_id = uuid4().hex

    # Determine file key and initial status based on R2 config
    if R2_CFG:
        key = f"videos/{sub_id}_{video_file.filename}"
        status = SubmissionStatus.processing
    else:
        key = None
        status = SubmissionStatus.completed

    submission = SubmissionModel(
        id=sub_id,
        content_id=content_id,
        platform=platform,
        file_name=key,
        status=status,
        created_at=_now_iso(),
        hotkey=hotkey,
        social_post_url=social_post_url,
    )

    save_submission_to_disk(submission)

    if R2_CFG:
        file_bytes = await video_file.read()
        file_like = io.BytesIO(file_bytes)
        # The key must not be None here
        background_tasks.add_task(background_upload, submission, file_like, key)

    return submission


# ───── Leaderboard Endpoint ─────────────────────────────────────────────
@app.get("/leaderboard")
def get_leaderboard():
    submissions = list_submissions()
    # Group submissions by hotkey (extracted from content_id or stored separately)
    creator_submissions = {}

    for submission in submissions:
        # Use stored hotkey or extract from content_id as fallback
        hotkey = submission.hotkey or (
            submission.content_id.split("_")[0]
            if "_" in submission.content_id
            else submission.content_id
        )

        if hotkey not in creator_submissions:
            creator_submissions[hotkey] = []
        creator_submissions[hotkey].append(submission)

    leaderboard = []
    for hotkey, user_submissions in creator_submissions.items():
        total_score = sum(
            1 for s in user_submissions if s.status == "completed"
        )  # Simple scoring
        daily_score = sum(
            1
            for s in user_submissions
            if s.status == "completed"
            and datetime.fromisoformat(s.created_at).date() == datetime.now().date()
        )

        latest_submission = (
            max(user_submissions, key=lambda s: s.created_at)
            if user_submissions
            else None
        )

        leaderboard.append(
            {
                "hotkey": hotkey,
                "total_score": total_score,
                "daily_score": daily_score,
                "latest_submission_url": (
                    latest_submission.file_name if latest_submission else None
                ),
            }
        )

    # Sort by total_score descending
    leaderboard.sort(key=lambda x: x["total_score"], reverse=True)
    return leaderboard


# ───── Creative Brief Endpoint ─────────────────────────────────────────────
@app.get("/creative-brief")
def get_creative_brief():
    submissions = list_submissions()
    # Return all completed submissions as "featured" for demo
    featured = [s for s in submissions if s.status == "completed"]
    featured.sort(key=lambda s: s.created_at, reverse=True)

    return [
        {
            "id": s.id,
            "content_id": s.content_id,
            "platform": s.platform,
            "file_name": s.file_name,
            "status": s.status,
            "created_at": s.created_at,
            "hotkey": s.hotkey,
            "social_post_url": s.social_post_url,
        }
        for s in featured
    ]


# ───── Creator Profile Endpoint ─────────────────────────────────────────────
@app.get("/creators/{hotkey}")
def get_creator_profile(hotkey: str = FastAPIPath(...)):
    submissions = list_submissions()
    # Find all submissions for this hotkey
    creator_submissions = []

    for submission in submissions:
        # Use stored hotkey or extract from content_id as fallback
        submission_hotkey = submission.hotkey or (
            submission.content_id.split("_")[0]
            if "_" in submission.content_id
            else submission.content_id
        )

        if submission_hotkey == hotkey:
            creator_submissions.append(submission)

    if not creator_submissions:
        raise HTTPException(status_code=404, detail="Creator not found")

    creator_submissions.sort(key=lambda s: s.created_at, reverse=True)

    return {
        "hotkey": hotkey,
        "submissions": [
            {
                "id": s.id,
                "content_id": s.content_id,
                "platform": s.platform,
                "file_name": s.file_name,
                "status": s.status,
                "created_at": s.created_at,
                "hotkey": s.hotkey,
                "social_post_url": s.social_post_url,
            }
            for s in creator_submissions
        ],
    }


# ----------------------------------------------------------------------------------
# Entry‑point (for *python fastapi_backend.py*) – optional, you can use uvicorn CLI
# ----------------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "mining-rest:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
