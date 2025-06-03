import json
import requests
import streamlit as st
from loguru import logger
from pydantic import BaseModel, ValidationError
from typing import Literal, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import uuid
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
# R2 Upload helpers
# --------------------------------------------------------------------------------------

def upload_video_to_r2(
    video_file, 
    r2_endpoint: str, 
    access_key: str, 
    secret_key: str, 
    bucket_name: str,
    bucket_id: str,
    public_domain: str = None
) -> str:
    """Upload video file to R2 bucket and return the direct URL."""
    
    try:
        # Create S3 client for R2
        s3_client = boto3.client(
            's3',
            endpoint_url=r2_endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name='auto'  # R2 uses 'auto' region
        )
        
        # Generate unique filename
        file_extension = os.path.splitext(video_file.name)[1]
        unique_filename = f"videos/{uuid.uuid4()}{file_extension}"
        
        # Upload file
        s3_client.upload_fileobj(
            video_file,
            bucket_name,
            unique_filename,
            ExtraArgs={'ContentType': 'video/mp4'}
        )
        
        public_url = f"https://pub-{BUCKET_ID}.r2.dev/{unique_filename}"
        
        print(f"✅ Upload successful!")
        print(f"🔗 Public sharing link: {public_url}")
        
        return public_url
        
    except NoCredentialsError:
        raise RuntimeError("R2 credentials not provided or invalid")
    except ClientError as e:
        raise RuntimeError(f"R2 upload failed: {e}")
    except Exception as e:
        raise RuntimeError(f"Upload error: {e}")


# --------------------------------------------------------------------------------------
# Streamlit UI
# --------------------------------------------------------------------------------------


def main():
    st.set_page_config(page_title="Submission Manager", layout="wide")

    st.title("📥 Submission Manager")
    st.caption("Add, update or remove submissions stored in a GitHub Gist.")

    # ---------------- Sidebar (connection settings) ----------------
    with st.sidebar:
        st.header("GitHub settings")
        api_key = st.text_input("Personal access token", type="password")
        gist_id = st.text_input("Gist ID")
        file_name = st.text_input("File name", value="submissions.jsonl")

        st.divider()
        
        st.header("R2 Storage settings")
        r2_endpoint = st.text_input("R2 Endpoint URL", placeholder="https://your-account-id.r2.cloudflarestorage.com")
        r2_access_key = st.text_input("R2 Access Key", type="password")
        r2_secret_key = st.text_input("R2 Secret Key", type="password")
        r2_bucket = st.text_input("R2 Bucket Name")
        r2_public_domain = st.text_input("Public Domain (optional)", placeholder="your-domain.com")

        if st.button("🔄 Load / refresh", disabled=not (api_key and gist_id)):
            try:
                st.session_state["subs"] = load_submissions(api_key, gist_id, file_name)    
                st.session_state.update(
                    api_key=api_key, gist_id=gist_id, file_name=file_name,
                    r2_endpoint=r2_endpoint, r2_access_key=r2_access_key,
                    r2_secret_key=r2_secret_key, r2_bucket=r2_bucket,
                    r2_public_domain=r2_public_domain
                )
                st.success("Submissions loaded.")
            except Exception as exc:
                st.error(str(exc))

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

    # ---------------- Add / update entry ----------------
    st.subheader("Add or update a submission")

    # Check if R2 settings are configured
    r2_configured = all([
        st.session_state.get("r2_endpoint"),
        st.session_state.get("r2_access_key"),
        st.session_state.get("r2_secret_key"),
        st.session_state.get("r2_bucket")
    ])

    if not r2_configured:
        st.warning("⚠️ Please configure R2 storage settings in the sidebar before uploading videos.")

    with st.form("submission_form", clear_on_submit=True):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            platform = st.selectbox(
                "Platform",
                ["youtube/video", "instagram/reel", "instagram/post"],
            )
            content_id = st.text_input("Content ID", placeholder="Enter unique content identifier")
        
        with col2:
            # Video upload section
            st.markdown("**Video Upload**")
            uploaded_file = st.file_uploader(
                "Choose MP4 video file",
                type=['mp4'],
                help="Upload your video file (MP4 format only)"
            )
            
            # Option to manually enter URL instead of upload
            manual_url = st.text_input(
                "Or enter direct video URL manually",
                placeholder="https://your-domain.com/video.mp4",
                help="Leave empty to upload file above"
            )

        # Show upload progress and preview
        if uploaded_file is not None:
            st.success(f"✅ File selected: {uploaded_file.name} ({uploaded_file.size / (1024*1024):.1f} MB)")
            
            # Video preview
            with st.expander("🎬 Preview video"):
                st.video(uploaded_file)

        colf = st.columns(3)
        save_btn = colf[0].form_submit_button("💾 Save", disabled=not r2_configured and not manual_url)
        cancel_btn = colf[1].form_submit_button("🔄 Reset")
        
        if save_btn:
            try:
                direct_video_url = ""
                
                # Determine video URL source
                if manual_url:
                    direct_video_url = manual_url
                elif uploaded_file is not None and r2_configured:
                    # Upload to R2
                    with st.spinner("🚀 Uploading video to R2..."):
                        direct_video_url = upload_video_to_r2(
                            uploaded_file,
                            st.session_state["r2_endpoint"],
                            st.session_state["r2_access_key"],
                            st.session_state["r2_secret_key"],
                            st.session_state["r2_bucket"],
                            st.session_state.get("r2_public_domain")
                        )
                        st.success(f"✅ Video uploaded successfully!")
                        st.info(f"📎 Direct URL: {direct_video_url}")
                else:
                    st.error("Please either upload a video file or enter a manual URL.")
                    st.stop()

                # Create submission
                new_sub = Submission(
                    platform=platform,
                    content_id=content_id,
                    direct_video_url=direct_video_url,
                )

                # Update or add submission
                replaced = False
                for i, s in enumerate(subs):
                    if s == new_sub:
                        subs[i] = new_sub
                        replaced = True
                        break
                if not replaced:
                    subs.append(new_sub)

                # Save to GitHub Gist
                save_submissions(
                    st.session_state["api_key"],
                    st.session_state["gist_id"],
                    st.session_state["file_name"],
                    subs,
                )
                st.session_state["subs"] = subs
                st.success("✅ Submission saved successfully!")
                st.experimental_rerun()
                
            except ValidationError as exc:
                st.error(f"❌ Validation error: {exc}")
            except Exception as exc:
                st.error(f"❌ Error: {exc}")

    # ---------------- Footer ----------------
    st.divider()
    
    with st.expander("ℹ️ Setup Instructions"):
        st.markdown("""
        ### GitHub Setup
        1. Create a GitHub Personal Access Token with **gist** scope
        2. Create a new Gist or use existing one
        3. Enter the Gist ID (from the URL)
        
        ### R2 Setup  
        1. Go to Cloudflare Dashboard → R2 Object Storage
        2. Create a bucket for your videos
        3. Generate R2 API tokens (Access Key & Secret Key)
        4. Get your R2 endpoint URL
        5. (Optional) Set up custom domain for public access
        """)
    
    st.caption(
        "🔒 Database lives in your own GitHub Gist. Videos are stored in your R2 bucket. You need a GitHub token with **gist** scope and R2 API credentials."
    )


if __name__ == "__main__":
    main()


#Bucket info:
# id: f190a221de18d9a334f1757abfdd226d // https://f190a221de18d9a334f1757abfdd226d.r2.cloudflarestorage.com

#access key: 041084871f89001cecf24a9aecfaa406
#secret key: f0904ad6664536c9558751029896dd8021f2711438cfaa7e5110959b003546e7
#https://f190a221de18d9a334f1757abfdd226d.r2.cloudflarestorage.com