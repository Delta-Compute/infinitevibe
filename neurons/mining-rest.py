"""
FastAPI backend replicating Streamlit Submission Manager functionalities.

Expose REST endpoints:
    GET  /                   Status check
    GET  /health             Simple health ping
    POST /git                Configure GitHub gist access and return current submissions
    PATCH /git               Update GitHub gist configuration
    POST /r2                 Configure Cloudflare R2 credentials (verifies access)
    PATCH /r2                Update R2 credentials
    GET  /submissions        List all submissions stored in the configured gist
    GET  /submissions/{id}   Retrieve a single submission by content_id
    DELETE /submissions/{id} Remove a submission and persist changes to the gist
    POST /submissions/upload-video  Upload a video file to R2 and return the public URL

Run with:
    uvicorn mining-rest:app --reload
"""
from __future__ import annotations

import json
import time
import os
from typing import List, Literal, Optional

import boto3
import requests
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

GITHUB_API_URL = "https://api.github.com"

app = FastAPI(title="Submission Manager API", version="0.1.0")

# --- CORS (adjust to your needs) ---------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
)

# ----------------------------------------------------------------------------------
# Pydantic data models
# ----------------------------------------------------------------------------------


class Submission(BaseModel):
    """A single content submission."""

    content_id: str
    platform: Literal["youtube/video", "instagram/reel", "instagram/post"]
    direct_video_url: str

    def __hash__(self) -> int:  # Allow set/dict operations
        return hash((self.platform, self.content_id))


class GitConfig(BaseModel):
    """Configuration required to access a GitHub Gist."""

    api_key: str = Field(
        ..., description="GitHub personal access token with *gist* scope"
    )
    gist_id: str
    file_name: str = "submissions.jsonl"


class R2Config(BaseModel):
    """Cloudflare R2 credentials and bucket information."""

    account_id: str
    bucket_name: str
    access_key_id: str
    secret_access_key: str
    public_link_id: str = Field(
        ...,
        description="Used to assemble public URL → https://pub-{public_link_id}.r2.dev/filename",
    )


# ----------------------------------------------------------------------------------
# Application‑level state (kept in memory; you can replace with DB/storage)
# ----------------------------------------------------------------------------------

app.state.git_config: Optional[GitConfig] = None
app.state.r2_config: Optional[R2Config] = None


# ----------------------------------------------------------------------------------
# Helper functions – GitHub Gist
# ----------------------------------------------------------------------------------

def _gh_request(method: str, url: str, api_key: str, **kwargs):
    """Wrapper around *requests.request* with GitHub‑specific headers."""

    headers = kwargs.pop("headers", {})
    headers.setdefault("Accept", "application/vnd.github+json")
    headers["Authorization"] = f"token {api_key}"

    try:
        resp = requests.request(method, url, headers=headers, timeout=15, **kwargs)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"GitHub network error: {exc}")

    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return resp


def load_submissions(cfg: GitConfig) -> List[Submission]:
    """Fetch and parse the submissions file from the given Gist."""

    gist_url = f"{GITHUB_API_URL}/gists/{cfg.gist_id}"
    gist_data = _gh_request("GET", gist_url, cfg.api_key).json()

    if cfg.file_name not in gist_data["files"]:
        return []

    raw_url = gist_data["files"][cfg.file_name]["raw_url"]
    raw_resp = requests.get(raw_url, timeout=15)
    raw_resp.raise_for_status()

    submissions: List[Submission] = []
    for ln, line in enumerate(raw_resp.text.splitlines(), start=1):
        if not line.strip():
            continue  # skip blanks
        try:
            submissions.append(Submission(**json.loads(line)))
        except Exception as exc:
            logger.warning(f"Malformed line {ln}: {exc}")

    return submissions


def save_submissions(cfg: GitConfig, subs: List[Submission]) -> None:
    """Persist *subs* back to the Gist (one‑JSON‑per‑line)."""

    content = "\n".join(s.model_dump_json(exclude_none=True) for s in subs) + "\n"
    payload = {"files": {cfg.file_name: {"content": content}}}

    _gh_request("PATCH", f"{GITHUB_API_URL}/gists/{cfg.gist_id}", cfg.api_key, json=payload)


# ----------------------------------------------------------------------------------
# Helper functions – Cloudflare R2
# ----------------------------------------------------------------------------------

def create_r2_client(cfg: R2Config):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{cfg.account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
        region_name="auto",
    )


def verify_r2(cfg: R2Config) -> bool:
    try:
        create_r2_client(cfg).head_bucket(Bucket=cfg.bucket_name)
        return True
    except (ClientError, NoCredentialsError) as exc:
        logger.error(f"R2 auth failed: {exc}")
        return False


def upload_to_r2(file_obj, filename: str, cfg: R2Config) -> str:
    """Upload *filename* to R2 and return its public URL."""

    client = create_r2_client(cfg)
    client.upload_fileobj(
        file_obj, cfg.bucket_name, filename, ExtraArgs={"ContentType": "video/mp4"}
    )
    return f"https://pub-{cfg.public_link_id}.r2.dev/{filename}"


# ----------------------------------------------------------------------------------
# Dependency helpers – ensure configuration exists before handling requests
# ----------------------------------------------------------------------------------

def require_git_config() -> GitConfig:
    if app.state.git_config is None:
        raise HTTPException(
            HTTP_400_BAD_REQUEST, "Git configuration not set. Call POST /git first."
        )
    return app.state.git_config


def require_r2_config() -> R2Config:
    if app.state.r2_config is None:
        raise HTTPException(
            HTTP_400_BAD_REQUEST, "R2 configuration not set. Call POST /r2 first."
        )
    return app.state.r2_config


# ----------------------------------------------------------------------------------
# API endpoints
# ----------------------------------------------------------------------------------


@app.get("/", summary="Status Check")
async def root():
    return {"status": "ok", "message": "Submission Manager API is running"}


@app.get("/health", summary="Health Check")
async def health():
    # You can expand this with deeper dependency checks (e.g. Bittensor ping)
    return {"healthy": True}


# ---- GitHub gist configuration ----------------------------------------------------


@app.post("/git", response_model=List[Submission], summary="Configure GitHub Gist access")
async def configure_git(cfg: GitConfig):
    """Verify credentials, store them in memory and return current submissions."""

    subs = load_submissions(cfg)
    app.state.git_config = cfg
    return subs


@app.get("/git", summary="Get GitHub Gist credentials")
async def get_git(cfg: GitConfig = Depends(require_git_config)):
    return cfg


@app.patch("/git", summary="Update GitHub Gist credentials")
async def update_git(cfg: GitConfig = Depends(require_git_config)):
    app.state.git_config = cfg
    return {"detail": "Git configuration updated"}


# ---- Cloudflare R2 configuration --------------------------------------------------

@app.get('/r2', summary='Get R2 credentials')
async def get_r2(cfg: R2Config = Depends(require_r2_config)):
    return cfg


@app.post("/r2", summary="Configure R2 credentials")
async def configure_r2(cfg: R2Config):
    if not verify_r2(cfg):
        raise HTTPException(HTTP_400_BAD_REQUEST, "R2 authentication failed")
    app.state.r2_config = cfg
    return {"detail": "R2 authentication successful"}


@app.patch("/r2", summary="Update R2 credentials")
async def update_r2(cfg: R2Config):
    app.state.r2_config = cfg
    return {"detail": "R2 configuration updated"}


# ---- Submission CRUD --------------------------------------------------------------


@app.get("/submissions", response_model=List[Submission], summary="List submissions")
async def list_submissions(git: GitConfig = Depends(require_git_config)):
    return load_submissions(git)


@app.get(
    "/submissions/{submission_id}",
    response_model=Submission,
    summary="Get a single submission",
)
async def get_submission(submission_id: str, git: GitConfig = Depends(require_git_config)):
    for sub in load_submissions(git):
        if sub.content_id == submission_id:
            return sub
    raise HTTPException(HTTP_404_NOT_FOUND, "Submission not found")


@app.delete("/submissions/{submission_id}", summary="Delete submission")
async def delete_submission(submission_id: str, git: GitConfig = Depends(require_git_config)):
    subs = load_submissions(git)
    remaining = [s for s in subs if s.content_id != submission_id]
    if len(remaining) == len(subs):
        raise HTTPException(HTTP_404_NOT_FOUND, "Submission not found")

    save_submissions(git, remaining)
    return {"detail": "Submission deleted"}


# ---- File upload ------------------------------------------------------------------


@app.post(
    "/submissions/upload-video",
    response_model=str,
    summary="Upload video file to R2 and return public URL",
)
async def upload_video(
    file: UploadFile = File(...),
    r2: R2Config = Depends(require_r2_config),
):
    """Store *file* in the configured R2 bucket and return its public URL."""

    filename = f"videos/{int(time.time())}_{file.filename}"
    try:
        url = upload_to_r2(file.file, filename, r2)
        return url
    except Exception as exc:
        logger.error(f"Upload failed: {exc}")
        raise HTTPException(502, f"Upload failed: {exc}")


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
