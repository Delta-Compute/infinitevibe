# Guide to mining

Technically, miner - ai video creator has 2 main tasks:
1. Create good ai video content, get high impressions, add signature "@tensorflix-studio <your_last_five_characters_of_your_wallet_address>" to the video caption.
2. Edit their submissions by our simple frontend then commit their submissions to bittensor network.

### Required format of a submission
- Content ID: unique id of the content, it can be any string. Length and pattern can be varied by the platform.
- Platform: platform of the content, it can be youtube, instagram, tiktok, etc.
- Direct video url: url that can access directly the video file. R2-Storage or S3 Storage is recommended.

### Guide to create a submission

1. Clone the repository

```bash
git clone https://github.com/Delta-Compute/tensorflix
```

2. Install dependencies
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv
uv sync
source .venv/bin/activate
```

3. Run the UI:
```bash
streamlit run neurons/mining.py
```
Then do instructions in the UI for updating your submissions on Github Gist.

4. Commit your submissions to bittensor network
```bash
python scripts/do_commit.py --netuid 52 --subtensor.network test --commit-message "gh_username:gh_gist_id" --wallet.name default --wallet.hotkey default
```
