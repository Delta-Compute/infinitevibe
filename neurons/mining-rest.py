# main.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import boto3
import httpx
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ───────────────────── Models ──────────────────────


class Submission(BaseModel):
    id: str
    content_id: str
    platform: str
    status: str = Field(default="completed")
    created_at: str
    file_name: Optional[str] = None  # object key within the R2 bucket


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


# ───────────────── In-memory “storage” ─────────────────
SUBMISSIONS: dict[str, Submission] = {}
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
    response_model=List[Submission],
    tags=["Submissions"],
    dependencies=[Depends(require_storage_ready)],
)
def list_submissions():
    return list(SUBMISSIONS.values())


@app.post(
    "/submissions/upload-video",
    status_code=201,
    response_model=Submission,
    tags=["Submissions"],
    dependencies=[Depends(require_storage_ready)],
)
async def upload_video(
    content_id: str = Form(...),
    platform: str = Form(...),
    video_file: UploadFile = File(...),
):
    sub_id = uuid.uuid4().hex
    submission = Submission(
        id=sub_id,
        content_id=content_id,
        platform=platform,
        status="processing",
        created_at=_now_iso(),
        file_name=video_file.filename,
    )
    SUBMISSIONS[sub_id] = submission

    try:
        s3 = _r2_client()
        key = f"{sub_id}/{video_file.filename}"
        video_file.file.seek(0)
        s3.upload_fileobj(video_file.file, R2_CFG.bucket_name, key)
        submission.status = "completed"
        submission.file_name = key
    except Exception as exc:  # noqa: BLE001
        submission.status = "failed"
        print("Upload error:", exc)
    finally:
        await video_file.close()
    return submission


def _finish_upload(file: UploadFile, sub_id: str):
    """Stream the file straight into Cloudflare R2."""
    s3 = _r2_client()
    key = f"{sub_id}/{file.filename}"
    try:
        file.file.seek(0)
        s3.upload_fileobj(file.file, R2_CFG.bucket_name, key)
        SUBMISSIONS[sub_id].status = "completed"
        SUBMISSIONS[sub_id].file_name = key
    except Exception:  # noqa: BLE001
        SUBMISSIONS[sub_id].status = "failed"
    finally:
        file.file.close()


@app.get(
    "/submissions/{submission_id}",
    response_model=Submission,
    tags=["Submissions"],
    dependencies=[Depends(require_storage_ready)],
)
def get_submission(submission_id: str):
    sub = SUBMISSIONS.get(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


@app.delete(
    "/submissions/{submission_id}",
    status_code=204,
    tags=["Submissions"],
    dependencies=[Depends(require_storage_ready)],
)
def delete_submission(submission_id: str):
    if SUBMISSIONS.pop(submission_id, None) is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    # best-effort delete from R2
    try:
        s3 = _r2_client()
        prefix = f"{submission_id}/"
        resp = s3.list_objects_v2(Bucket=R2_CFG.bucket_name, Prefix=prefix)
        for obj in resp.get("Contents", []):
            s3.delete_object(Bucket=R2_CFG.bucket_name, Key=obj["Key"])
    except Exception:  # noqa: BLE001
        pass  # ignore – deletion is optional


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
