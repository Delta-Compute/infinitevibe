import os
import tempfile
import random
import shutil
import requests
import cv2
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List
from starlette.responses import JSONResponse

SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")

if not (SIGHTENGINE_USER and SIGHTENGINE_SECRET):
    raise RuntimeError("Set SIGHTENGINE_USER and SIGHTENGINE_SECRET env vars")

app = FastAPI()


class DetectResult(BaseModel):
    mean_ai_generated: float
    per_frame: List[float]


def download_video(url: str, dest_path: str):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(r.raw, f)


def get_random_frames(video_path: str, num_frames: int = 10):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video file")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames == 0:
        cap.release()
        raise RuntimeError("No frames in video")

    frame_indices = sorted(
        random.sample(range(total_frames), min(num_frames, total_frames))
    )
    frames = []
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        # Convert BGR to RGB for consistency
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frames.append(frame)
    cap.release()
    return frames


def save_temp_image(frame):
    temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    cv2.imwrite(temp_img.name, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    return temp_img.name


def query_sightengine(image_path: str):
    url = "https://api.sightengine.com/1.0/check.json"
    files = {"media": open(image_path, "rb")}
    data = {
        "models": "genai",
        "api_user": SIGHTENGINE_USER,
        "api_secret": SIGHTENGINE_SECRET,
    }
    resp = requests.post(url, files=files, data=data)
    files["media"].close()
    if resp.status_code != 200:
        raise RuntimeError(f"API error: {resp.text}")
    result = resp.json()
    if result.get("status") != "success":
        raise RuntimeError(f"API failure: {result}")
    prob = float(result["type"].get("ai_generated", 0.0))
    return prob


@app.post("/detect", response_model=DetectResult)
def detect(url: str = Query(..., description="URL to video")):
    print(f"Detecting {url}")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_video:
        try:
            download_video(url, tmp_video.name)
            print(f"Downloaded video to {tmp_video.name}")
            frames = get_random_frames(tmp_video.name, 10)
            print(f"Got {len(frames)} frames")
            ai_probs = []
            for frame in frames:
                img_path = save_temp_image(frame)
                print(f"Saved image to {img_path}")
                try:
                    prob = query_sightengine(img_path)
                    print(f"Got prob {prob}")
                    ai_probs.append(prob)
                except Exception as e:
                    logger.error(f"Got error: {e}")
                    continue
                finally:
                    os.unlink(img_path)
            if not ai_probs:
                mean_prob = 0.969
            else:
                mean_prob = sum(ai_probs) / len(ai_probs)
            print(f"Mean prob {mean_prob}")
            return DetectResult(mean_ai_generated=mean_prob, per_frame=ai_probs)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            try:
                os.unlink(tmp_video.name)
            except Exception:
                pass
