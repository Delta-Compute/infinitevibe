# Tensorflix Mining Guide

## Overview

As a miner (AI video creator), your primary responsibilities are:

1. **Create Engaging AI Video Content**: Produce high-quality AI-generated videos that attract significant impressions. Ensure each video caption includes your signature in the following format:

   ```
   Made with @infinitevibe.ai on #bittensor --- <your_last_five_characters_of_your_hotkey_ss58_address>
   ```



2. **Submit and Edit Content**: Utilize our frontend interface to edit your submissions and commit them to the Bittensor network.

---

## Submission Format

Each submission should adhere to the following structure:

* **Content ID**: A unique identifier for your content. This can be any string, with length and pattern varying based on the platform.

* **Platform**: The platform where the content is published (e.g., YouTube, Instagram, TikTok).

* **Direct Video URL**: A URL that provides direct access to the video file. It's recommended to use R2 Storage or S3 Storage for hosting.

---

## Setting Up Required Credentials

### 1. GitHub Gist Personal Access Token (PAT)

To enable the creation and editing of Gists via the API, follow these steps to generate a GitHub PAT with the necessary permissions:

1. **Access Developer Settings**:

   * Navigate to your GitHub account and click on your profile picture in the top-right corner.
   * Select **Settings** from the dropdown menu.
   * In the left sidebar, click on **Developer settings**.

2. **Generate a New Token**:

   * Click on **Personal access tokens**, then select **Tokens (classic)**.
   * Click **Generate new token**.

3. **Configure the Token**:

   * **Note**: Provide a descriptive name for the token (e.g., "Tensorflix Gist Access").
   * **Expiration**: Set an appropriate expiration date or choose "No expiration" based on your preference.
   * **Scopes**: Check the box for `gist` to grant access to create and edit Gists.

4. **Generate and Save the Token**:

   * Click **Generate token**.
   * **Important**: Copy and securely store the generated token immediately, as it will not be displayed again.

For more detailed information, refer to GitHub's official documentation on managing personal access tokens.

### 2. Create a new Gist

1. Go to [Github Gist](https://gist.github.com/)
2. Click on **New Gist**
3. Give your Gist a name: `submissions.jsonl`
4. Paste `{}` to the content field
5. Click on **Create Gist**
6. Grab the Gist ID from the URL. Example: `https://gist.github.com/your_username/your_gist_id`

<img width="1062" alt="image" src="https://github.com/user-attachments/assets/604a7d7a-d4cb-48f4-9a6e-61cf28569b7a" />


### 3. Cloudflare R2 Bucket and API Credentials

To store and manage your video files, you'll need to set up a Cloudflare R2 bucket and obtain the necessary API credentials:

1. **Create a Cloudflare Account**:

   * If you don't have one already, sign up at [Cloudflare](https://dash.cloudflare.com/sign-up).

2. **Access R2 in the Dashboard**:

   * Log in to your Cloudflare account.
   * Navigate to the **R2** section from the left-hand panel.

3. **Create a New Bucket**:

   * Click on **Create Bucket**.
   * Provide a unique name for your bucket and select the desired jurisdiction (e.g., `default`, `EU`).
   * Click **Create** to finalize.

4. **Generate API Tokens**:

   * In the R2 section, click on **Manage R2 API Tokens**.
   * Click **Create API Token**.
   * **Token Name**: Assign a name like "Tensorflix R2 Access".
   * **Permissions**: Select **Admin Read & Write** to allow full access.
   * Click **Create API Token**.
   * **Important**: Copy and securely store the **Access Key ID** and **Secret Access Key** immediately, as they will not be displayed again.

5. **Retrieve Account ID and Public Development URL**:

   * **Account ID**: Found in the **Account Home** section of your Cloudflare dashboard.
   * **Public Development URL**:
   - Go to Bucket > Settings > Public Development URL > Click Enable > Copy the ID of URL. Example `https://pub-THIS_ID.r2.dev`

---

## Creating and Submitting Content

Ensure that you have the following credentials:
- GitHub Gist ID
- Github Gist Personal Access Token
- Github Username
- Cloudflare R2 Bucket Account ID
- Cloudflare R2 Bucket Public Development URL
- Cloudflare R2 Bucket Access Key ID
- Cloudflare R2 Bucket Secret Access Key

Follow these steps to set up your environment and submit your content:

1. **Clone the Tensorflix Repository**:

   ```bash
   git clone https://github.com/Delta-Compute/infinitevibe
   ```



2. **Install Dependencies**:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   export PATH="$HOME/.local/bin:$PATH"
   uv venv
   uv sync
   source .venv/bin/activate
   ```



3. **Launch the Frontend Interface**:

   ```bash
   streamlit run neurons/mining.py
   ```



* Follow the on-screen instructions to edit and prepare your submissions.

Basic usage for adding a new submission:
```
1. Fill in the credentials and information about Gist and R2 Storage at sidebar
2. Select video from your local machine, then click on **Upload Video**
3. Fill in the information about the video: `content_id` you get from platform, `platform` you choose from dropdown, `direct_video_url` you automatically get from R2 Storage
4. Click on **Submit**
5. You can see the video in the Gist, and the video will be uploaded to R2 Storage
```

4. **Commit Submissions to the Bittensor Network**:

   ```bash
   python scripts/do_commit.py --netuid 89 --subtensor.network finney --commit-message "gh_username:gh_gist_id" --wallet.name default --wallet.hotkey default
   ```



* Replace `gh_username` and `gh_gist_id` with your actual GitHub username and Gist ID, respectively.
* Replace wallet name and hotkey with your actual wallet name and hotkey, respectively.

---

## Additional Resources

* **GitHub Personal Access Tokens**: For more information on creating and managing PATs, visit GitHub's documentation.

* **Cloudflare R2 Authentication**: Detailed guidance on R2 API tokens can be found in Cloudflare's documentation.
