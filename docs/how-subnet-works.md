# TensorFlix Subnet: Incentive Mechanism & Validation

## 1. Overview

The TensorFlix subnet aims to incentivize the creation, curation, and promotion of engaging video and image content on popular social media platforms like YouTube and Instagram. Miners (content producers/curators) are rewarded with $TAO based on the performance and validity of their submitted content. Validators are responsible for verifying these submissions, assessing their quality and engagement, and setting weights on the Bittensor network accordingly.

The core pipeline involves:
1.  **Miners:** Submitting links to their content hosted on supported platforms (YouTube, Instagram) via a public Gist. This content must contain a specific signature linking it to their Bittensor hotkey.
2.  **Validators:** Periodically fetching these submissions, verifying their authenticity, checking for AI-generated content, retrieving performance metrics (views, likes, comments), and scoring them.
3.  **Bittensor Network:** Validators use these scores to set weights for miners, influencing their $TAO rewards.

## 2. Key Components

*   **Miners (Producers):** Participants who create or curate content and submit it to the network.
*   **Validators:** Participants running the validator script (`validator.py`) to assess miner contributions.
*   **Submissions:** Links to content (YouTube videos, Instagram posts/reels) provided by miners.
*   **AI Detector Service:** An external microservice (`ai_detector/main.py`) that analyzes video content to determine the likelihood of it being AI-generated.
*   **Platform Tracker Service:** An external microservice (`platform_tracker/main.py`) that fetches metadata and engagement statistics (views, likes, comments, description/caption) from social media platforms.
*   **Configuration (`config.py`):** Defines network parameters, API keys, service URLs, and scoring thresholds.

## 3. Miner Responsibilities (How to Participate)

To participate as a miner and earn rewards, you must:

1.  **Create/Curate Content:** Produce or find high-quality video or image content suitable for YouTube or Instagram.
2.  **Include Signature:**
    *   For **YouTube videos**, include the following signature in the video's **description**:
        `Made with @infinitevibe.ai on #bittensor\n{YOUR_HOTKEY_LAST_5_CHARS}`
        (e.g., `Made with @infinitevibe.ai on #bittensor\nAbCdE`)
    *   For **Instagram posts/reels**, include the same signature in the **caption**.
    *   This signature is crucial for validators to verify your ownership and participation. The exact format is defined by `CONFIG.get_signature_post(hotkey)`.
3.  **Publish Content:** Upload your content to YouTube or Instagram.
4.  **Create a Gist:**
    *   Create a public GitHub Gist.
    *   Each line in the Gist should be a JSON object representing a single `Submission`.
    *   The format for each `Submission` JSON object is:
        ```json
        {
          "content_id": "YOUR_YOUTUBE_VIDEO_ID_OR_INSTAGRAM_MEDIA_ID",
          "platform": "youtube/video" | "instagram/reel" | "instagram/post",
          "direct_video_url": "DIRECT_URL_TO_THE_VIDEO_FILE_FOR_AI_DETECTION"
        }
        ```
        *   `content_id`: The unique ID of the video/post on the platform (e.g., `dQw4w9WgXcQ` for a YouTube video).
        *   `platform`: Specifies the platform and content type. Must be one of `CONFIG.allowed_platforms`.
        *   `direct_video_url`: A direct, publicly accessible URL to the video file (e.g., `.mp4`). This is used by the AI Detector service.
    *   Example Gist content:
        ```
        {"content_id": "video_id_1", "platform": "youtube/video", "direct_video_url": "https://example.com/video1.mp4"}
        {"content_id": "post_id_xyz", "platform": "instagram/post", "direct_video_url": "https://example.com/insta_post_video.mp4"}
        ```
5.  **Register on Subnet:** When registering your neuron (miner) on the TensorFlix subnet (netuid specified in `CONFIG.netuid`, e.g., 89), you must provide your Gist commit identifier in the format `<github_username>:<gist_id>` as part of your neuron's metadata. Validators will use this to find your submissions.

## 4. Validation Process

Validators execute the `validator.py` script, which orchestrates the validation and scoring pipeline.

### 4.1. Initialization (`_bootstrap`)

1.  **Configuration & Setup:**
    *   Parses command-line arguments (e.g., `--netuid`, wallet, subtensor).
    *   Loads environment variables (e.g., `MONGO_URI`, `SIGHTENGINE_USER`, `SIGHTENGINE_SECRET`).
    *   Initializes Bittensor `wallet`, `subtensor` (connection to the Bittensor network), and `metagraph`.
    *   Connects to MongoDB using `MONGO_URI`.
2.  **Validator Instance:** Creates an instance of `TensorFlixValidator`.
3.  **Run Loop:** Calls `validator.run()` to start the main validation loop.

### 4.2. Main Validation Loop (Conceptual - within `TensorFlixValidator.run()`)

The `TensorFlixValidator` continuously performs the following actions:

1.  **Metagraph Sync:** Periodically synchronizes with the Bittensor metagraph to get the latest list of active neurons (miners and other validators) on the subnet.
2.  **Fetch Miner Submissions:**
    *   For each active miner identified in the metagraph:
        *   Retrieves the miner's `PeerMetadata`, which includes their Gist commit string (`username:gist_id`).
        *   Calls `PeerMetadata.update_submissions()`:
            *   Constructs the raw Gist URL (e.g., `https://gist.githubusercontent.com/{username}/{gist_id}/raw`).
            *   Fetches the content of the Gist.
            *   Parses each line as a `Submission` JSON object.
            *   Filters submissions based on `CONFIG.allowed_platforms`.
            *   Updates the `submissions` list within the `PeerMetadata` object.
    *   This step is repeated periodically, controlled by `CONFIG.submission_update_interval`.

3.  **Process and Score Submissions:**
    For each `Submission` from each miner:

    *   **Step A: AI Content Detection**
        1.  The validator takes the `submission.direct_video_url`.
        2.  It makes a POST request to the AI Detector service (`CONFIG.service_ai_detector_url` e.g., `http://localhost:12002/detect?url={direct_video_url}`).
        3.  The AI Detector service:
            *   Downloads the video from `direct_video_url`.
            *   Extracts a number of random frames (e.g., 10).
            *   For each frame, saves it as a temporary image.
            *   Sends the image to the SightEngine API (`https://api.sightengine.com/1.0/check.json`) with the model `genai`.
            *   SightEngine returns a probability score indicating how likely the frame is AI-generated.
            *   The service calculates the mean AI-generated probability across all sampled frames.
        4.  The validator receives the `mean_ai_generated` score (let's call this `ai_score_value`) from the AI Detector.

    *   **Step B: Platform Metrics Retrieval & Signature Verification**
        1.  The validator uses `submission.platform` and `submission.content_id`.
        2.  It makes a GET request to the Platform Tracker service (`CONFIG.service_platform_tracker_url`, e.g., `http://localhost:12001/get_metrics/{platform}/{content_type}/{content_id}`).
        3.  The Platform Tracker service:
            *   Identifies the correct tracker (e.g., `YouTubeTracker`, `InstagramTracker`).
            *   **YouTube:** Uses the Google YouTube Data API v3 to fetch video details (title, description, statistics like views, likes, comments).
            *   **Instagram:** Uses the Apify API (Instagram Scrapers) to fetch post/reel details (caption, likes, comments, views).
            *   Returns the metadata as a `YoutubeVideoMetadata` or `InstagramPostMetadata` object.
        4.  The validator receives this platform metric object (let's call it `metric_data`). This `metric_data` includes the actual description/caption of the content.
        5.  The `ai_score_value` obtained from Step A is assigned to `metric_data.ai_score`.
        6.  The validator calls `metric_data.check_signature(miner_hotkey)`. This method checks if the required signature (e.g., `Made with @infinitevibe.ai on #bittensor\n{hotkey_suffix}`) is present in the `metric_data.description` (for YouTube) or `metric_data.caption` (for Instagram).

    *   **Step C: Scoring (`Performance.get_score`)**
        1.  A `Performance` object is used to calculate a score for the miner's content. This object stores `platform_metrics_by_interval` (though the provided snippets suggest a single point calculation per validation cycle for simplicity in this explanation).
        2.  The `get_score()` method iterates through the available `metric_data` (potentially from different time intervals, if tracked).
        3.  For each `metric_data` point:
            *   **Condition 1: Signature Check:** `metric_data.check_signature(miner_hotkey)` must be `True`.
            *   **Condition 2: AI Score Threshold:** `metric_data.ai_score > CONFIG.ai_generated_score_threshold`.
                *   _Note: This condition implies that content is considered valid if its AI-generated score is **above** the threshold. This might be intended to filter out content that is *not* sufficiently AI-assisted or to ensure a certain style, or it could be a misinterpretation of the desired logic (often, one might expect `ai_score < threshold` to penalize AI content). The documentation reflects the code as written._
            *   If **both** conditions are met:
                *   The `metric_data.to_scalar()` method is called. This typically calculates an engagement score (e.g., `(view_count + like_count + comment_count) / 3`).
                *   This scalar value is incorporated into an Exponential Moving Average (EMA) score: `score = metric.to_scalar() * alpha + score * (1 - alpha)`, where `alpha` is a smoothing factor (e.g., 0.95).
            *   If **either** condition is `False`:
                *   The score for that specific metric point effectively becomes `0.0`, resetting or significantly reducing the EMA for that content.
        4.  The final EMA score from `Performance.get_score()` represents the quality and engagement of that particular submission, adjusted for validity checks.

4.  **Aggregating Scores & Setting Weights:**
    *   The validator aggregates the scores from all valid submissions for each miner.
    *   These aggregated scores are then normalized across all miners.
    *   Periodically (defined by `CONFIG.set_weights_interval`), the validator calls `subtensor.set_weights()` to publish these normalized scores (as weights) to the Bittensor network.
    *   Miners with higher weights receive a larger share of $TAO emissions for that epoch.
    *   `CONFIG.version_key` is used to signal changes in scoring logic, allowing the network to adapt.

### 4.3. Data Storage

*   MongoDB is used by the validator, likely for caching fetched data, tracking submission history, or managing state between validation cycles. The exact usage is specific to the `TensorFlixValidator` implementation.

## 5. Key Services

### 5.1. AI Detector Service (`ai_detector/main.py`)

*   **Endpoint:** `POST /detect`
*   **Input:** `url` (direct video URL) as a query parameter.
*   **Process:**
    1.  Downloads the video.
    2.  Extracts random frames.
    3.  Queries SightEngine API (`models=genai`) for each frame.
    4.  Calculates the mean AI-generated probability.
*   **Output:** `DetectResult` (JSON: `{"mean_ai_generated": float, "per_frame": List[float]}`)
*   **Dependencies:** `SIGHTENGINE_USER`, `SIGHTENGINE_SECRET` environment variables.

### 5.2. Platform Tracker Service (`platform_tracker/main.py`)

*   **Endpoints:**
    *   `GET /get_metrics/{platform}/{content_type}/{content_id}`
    *   `GET /platforms`
    *   `GET /health`
*   **Process (`/get_metrics`):**
    1.  Takes platform (e.g., "youtube", "instagram"), content type (e.g., "video", "post"), and content ID.
    2.  Uses the appropriate tracker (`YouTubeTracker` or `InstagramTracker`).
    3.  `YouTubeTracker`: Uses Google YouTube Data API. Requires `YOUTUBE_API_KEY`.
    4.  `InstagramTracker`: Uses Apify Client (Instagram scrapers). Requires `APIFY_API_KEY`.
    5.  Fetches metadata (title, description/caption, views, likes, comments, etc.).
*   **Output (`/get_metrics`):** JSON representation of `YoutubeVideoMetadata` or `InstagramPostMetadata`.
*   **Dependencies:** Environment variables for API keys (e.g., `YOUTUBE_API_KEY`, `APIFY_API_KEY` - specific names in `platform_tracker/config.py`).

## 6. Important Configuration Values (`config.py`)

*   `netuid`: The unique ID of the TensorFlix subnet.
*   `allowed_platforms`: Tuple of supported platforms (e.g., `"youtube/video"`, `"instagram/reel"`).
*   `submission_update_interval`: How often validators refresh miner submissions from Gists (in seconds).
*   `set_weights_interval`: How often validators set weights on the Bittensor network (in seconds).
*   `ai_generated_score_threshold`: The threshold for the AI-generated score. Content with `ai_score` *above* this threshold passes this check.
*   `service_platform_tracker_url`: URL for the Platform Tracker service.
*   `service_ai_detector_url`: URL for the AI Detector service.
*   `get_signature_post(hotkey)`: Method defining the exact signature string miners must include.

This incentive mechanism is designed to reward miners for high-quality, engaging, and properly attributed content, while validators ensure fairness and adherence to the subnet's rules.
