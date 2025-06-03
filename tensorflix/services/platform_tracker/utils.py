import requests
def filter_AI_video(video_url: str, start_time: int, end_time: int, fps: int = 24) -> bool:
    api_endpoint = "https://api.bitmind.ai/oracle/v1/34/detect-video"
    payload = {
        "video": video_url,
        "startTime": start_time,
        "endTime": end_time,
        "fps": fps,
        "rich": True
    }
    headers = {
        "Authorization": "Bearer oracle-f3459c05-7e7e-4335-add1-247fef4d0c68:17eb465d"
    }
    response = requests.post(
        api_endpoint,
        headers=headers,
        json=payload
    )
    is_AI = response.json()["isAI"]
    print("is AI:", is_AI)
    return is_AI

def filter_caption_video(video_caption: str) -> bool:
    list_of_valid_captions = [
        "tensorflix bittensor"
        "AI generated video",
    ]
    # if there is any caption in list_of_valid_captions don't have in video_caption return False
    if any(caption in video_caption for caption in list_of_valid_captions):
        return False
    return True

if __name__ == "__main__":
    filter_AI_video(
        video_url="https://pub-a55bd0dbae3c4afd86bd066961ab7d1e.r2.dev/test_10secs.mov",
        start_time=1,
        end_time=5,
        fps=24
    )
