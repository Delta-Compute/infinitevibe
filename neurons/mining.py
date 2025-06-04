import json
import requests
import streamlit as st
from loguru import logger
from pydantic import BaseModel, ValidationError
from typing import Literal, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import tempfile
import os

# --------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------


class Submission(BaseModel):
    """A single content submission."""

    content_id: str
    platform: Literal["youtube/video", "instagram/reel", "instagram/post"]
    direct_video_url: str

    def __hash__(self) -> int:  # Allow "set"/dict operations
        return hash((self.platform, self.content_id))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Submission) and (
            self.platform,
            self.content_id,
        ) == (other.platform, other.content_id)


# --------------------------------------------------------------------------------------
# GitHub Gist helpers
# --------------------------------------------------------------------------------------

GITHUB_API_URL = "https://api.github.com"


def _gh_request(method: str, url: str, api_key: str, **kwargs):
    """Wrapper around requests.request with GitHub-specific headers & basic error handling."""

    headers = kwargs.pop("headers", {})
    headers.setdefault("Accept", "application/vnd.github+json")
    headers["Authorization"] = f"token {api_key}"
    try:
        response = requests.request(method, url, headers=headers, timeout=15, **kwargs)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    if not response.ok:
        raise RuntimeError(f"GitHub API {response.status_code}: {response.text}")
    return response


@st.cache_data(show_spinner=False)
def load_submissions(api_key: str, gist_id: str, file_name: str) -> List[Submission]:
    """Return all submissions stored in the given Gist file. Missing file ⇒ empty list."""

    gist_url = f"{GITHUB_API_URL}/gists/{gist_id}"
    gist_data = _gh_request("GET", gist_url, api_key).json()

    if file_name not in gist_data["files"]:
        return []

    raw_url = gist_data["files"][file_name]["raw_url"]
    raw_resp = requests.get(raw_url, timeout=15)
    raw_resp.raise_for_status()

    submissions: List[Submission] = []
    for ln, line in enumerate(raw_resp.text.splitlines(), start=1):
        if not line.strip():
            continue  # skip blanks
        try:
            submissions.append(Submission(**json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(f"Skipping malformed line {ln}: {exc}")
    return submissions


def save_submissions(
    api_key: str, gist_id: str, file_name: str, submissions: List[Submission]
) -> None:
    """Persist the list of submissions back to the Gist (one-line-per-JSON)."""

    content = (
        "\n".join(s.model_dump_json(exclude_none=True) for s in submissions) + "\n"
    )
    payload = {"files": {file_name: {"content": content}}}

    _gh_request("PATCH", f"{GITHUB_API_URL}/gists/{gist_id}", api_key, json=payload)


# --------------------------------------------------------------------------------------
# R2 Storage helpers
# --------------------------------------------------------------------------------------


def create_r2_client(account_id: str, access_key_id: str, secret_access_key: str):
    """Create and return an R2 client."""
    return boto3.client(
        's3',
        endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name='auto'
    )


def verify_r2_authentication(account_id: str, bucket_name: str, access_key_id: str, secret_access_key: str) -> bool:
    """Verify R2 storage authentication by attempting to list bucket contents."""
    try:
        client = create_r2_client(account_id, access_key_id, secret_access_key)
        client.head_bucket(Bucket=bucket_name)
        return True
    except (ClientError, NoCredentialsError) as e:
        logger.error(f"R2 authentication failed: {e}")
        return False


def upload_video_to_r2(
    video_file, 
    filename: str, 
    account_id: str, 
    bucket_name: str, 
    access_key_id: str, 
    secret_access_key: str,
    public_link_id: str
) -> str:
    """Upload video to R2 storage and return the public URL."""
    try:
        client = create_r2_client(account_id, access_key_id, secret_access_key)
        
        # Upload the file
        client.upload_fileobj(
            video_file,
            bucket_name,
            filename,
            ExtraArgs={'ContentType': 'video/mp4'}
        )
        
        # Generate public URL
        public_url = f"https://pub-{public_link_id}.r2.dev/{filename}"
        return public_url
        
    except Exception as e:
        logger.error(f"Failed to upload video to R2: {e}")
        raise


# --------------------------------------------------------------------------------------
# Streamlit UI
# --------------------------------------------------------------------------------------


def main():
    st.set_page_config(page_title="Submission Manager", layout="wide")

    st.title("📥 Submission Manager")
    st.caption("Add, update or remove submissions stored in a GitHub Gist.")

    # ---------------- Sidebar (connection settings) ----------------
    with st.sidebar:
        st.header("GitHub Settings")
        api_key = st.text_input("Personal access token", type="password")
        gist_id = st.text_input("Gist ID")
        file_name = st.text_input("File name", value="submissions.jsonl")

        if st.button("🔄 Load / refresh", disabled=not (api_key and gist_id)):
            try:
                st.session_state["subs"] = load_submissions(api_key, gist_id, file_name)
                st.session_state.update(
                    api_key=api_key, gist_id=gist_id, file_name=file_name
                )
                st.success("Submissions loaded.")
            except Exception as exc:
                st.error(str(exc))

        st.divider()
        
        # R2 Storage Configuration
        st.header("R2 Storage Settings")
        r2_account_id = st.text_input("Account ID")
        r2_bucket_name = st.text_input("Bucket Name")
        r2_access_key_id = st.text_input("Access Key ID")
        r2_secret_key = st.text_input("Secret Access Key", type="password")
        r2_public_link_id = st.text_input("Public Link ID", help="Used for generating public URLs: https://pub-{PUBLIC_LINK_ID}.r2.dev/filename")
        
        if st.button("🔐 Verify Authentication", disabled=not (r2_account_id and r2_bucket_name and r2_access_key_id and r2_secret_key)):
            try:
                if verify_r2_authentication(r2_account_id, r2_bucket_name, r2_access_key_id, r2_secret_key):
                    st.success("✅ R2 authentication successful!")
                    st.session_state.update(
                        r2_account_id=r2_account_id,
                        r2_bucket_name=r2_bucket_name,
                        r2_access_key_id=r2_access_key_id,
                        r2_secret_key=r2_secret_key,
                        r2_public_link_id=r2_public_link_id,
                        r2_authenticated=True
                    )
                else:
                    st.error("❌ R2 authentication failed!")
                    st.session_state["r2_authenticated"] = False
            except Exception as exc:
                st.error(f"❌ Authentication error: {exc}")
                st.session_state["r2_authenticated"] = False

    # Guard – no data until loaded
    subs: List[Submission] = st.session_state.get("subs", [])
    if not subs:
        st.info("No data loaded yet – enter credentials and click **Load / refresh**.")
        st.stop()

    # ---------------- Table of current submissions ----------------
    st.subheader("Current submissions")

    col_cfg = [2, 3, 5, 1]  # flex columns width
    hdr = st.columns(col_cfg)
    hdr[0].markdown("**Platform**")
    hdr[1].markdown("**Content ID**")
    hdr[2].markdown("**Direct video URL**")
    hdr[3].markdown("**Actions**")

    for idx, sub in enumerate(subs):
        c1, c2, c3, c4 = st.columns(col_cfg)
        c1.write(sub.platform)
        c2.write(sub.content_id)
        c3.write(sub.direct_video_url)
        if c4.button("🗑️", key=f"del-{idx}"):  # delete row
            subs.pop(idx)
            save_submissions(
                st.session_state["api_key"],
                st.session_state["gist_id"],
                st.session_state["file_name"],
                subs,
            )
            st.session_state["subs"] = subs
            st.experimental_rerun()

    st.divider()

    # ---------------- Video Upload Section ----------------
    if st.session_state.get("r2_authenticated", False):
        st.subheader("📹 Upload Video to R2 Storage")
        
        uploaded_file = st.file_uploader(
            "Choose a video file", 
            type=['mp4', 'mov', 'avi', 'mkv'],
            help="Upload a video file to automatically generate the direct video URL"
        )
        
        if uploaded_file is not None:
            st.info(f"File selected: {uploaded_file.name} ({uploaded_file.size / (1024*1024):.2f} MB)")
            
            if st.button("⬆️ Upload to R2 Storage"):
                try:
                    with st.spinner("Uploading video to R2 storage..."):
                        # Generate a unique filename
                        import time
                        timestamp = int(time.time())
                        filename = f"videos/{timestamp}_{uploaded_file.name}"
                        
                        # Upload to R2
                        public_url = upload_video_to_r2(
                            uploaded_file,
                            filename,
                            st.session_state["r2_account_id"],
                            st.session_state["r2_bucket_name"],
                            st.session_state["r2_access_key_id"],
                            st.session_state["r2_secret_key"],
                            st.session_state["r2_public_link_id"]
                        )
                        
                        st.success(f"✅ Video uploaded successfully!")
                        st.info(f"Public URL: {public_url}")
                        st.session_state["uploaded_video_url"] = public_url
                        
                except Exception as exc:
                    st.error(f"Upload failed: {exc}")
        
        st.divider()

    # ---------------- Add / update entry ----------------
    st.subheader("Add or update a submission")

    with st.form("submission_form", clear_on_submit=True):
        platform = st.selectbox(
            "Platform",
            ["youtube/video", "instagram/reel", "instagram/post"],
        )
        content_id = st.text_input("Content ID")
        
        # Auto-fill direct video URL if video was uploaded
        default_url = st.session_state.get("uploaded_video_url", "")
        direct_video_url = st.text_input(
            "Direct video URL", 
            value=default_url,
            help="Upload a video above to auto-fill this field, or enter manually"
        )

        colf = st.columns(2)
        save_btn = colf[0].form_submit_button("💾 Save")
        cancel_btn = colf[1].form_submit_button("Reset")

        if save_btn:
            try:
                new_sub = Submission(
                    platform=platform,
                    content_id=content_id,
                    direct_video_url=direct_video_url,
                )

                replaced = False
                for i, s in enumerate(subs):
                    if s == new_sub:
                        subs[i] = new_sub
                        replaced = True
                        break
                if not replaced:
                    subs.append(new_sub)

                save_submissions(
                    st.session_state["api_key"],
                    st.session_state["gist_id"],
                    st.session_state["file_name"],
                    subs,
                )
                st.session_state["subs"] = subs
                # Clear the uploaded video URL after saving
                if "uploaded_video_url" in st.session_state:
                    del st.session_state["uploaded_video_url"]
                st.success("Submission saved.")
                st.experimental_rerun()
            except ValidationError as exc:
                st.error(f"Validation error: {exc}")
            except Exception as exc:
                st.error(str(exc))

    # ---------------- Footer ----------------
    st.caption(
        "Database lives in your own GitHub Gist. Videos are stored in your R2 bucket. "
        "You need a GitHub token with **gist** scope and R2 credentials."
    )


if __name__ == "__main__":
    main()
