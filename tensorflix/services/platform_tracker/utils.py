import requests
import requests
import json
import cv2
from io import BytesIO

def filter_AI_video(video_url: str, start_time: int, end_time: int, fps: int = 24) -> bool:
    params = {
        'models': 'genai',
        'api_user': '1000474889',
        'api_secret': 'g6MKC4ybq9PMxA2ESii9KDGYHwhjtkfX'
    }

    response = requests.get(video_url)
    with open("request_video.mp4", 'wb') as f:
        f.write(response.content)

    video_capture = cv2.VideoCapture("request_video.mp4")
    ret, frame = video_capture.read()

    if ret:
        _, buffer = cv2.imencode('.jpg', frame)
        image_file = BytesIO(buffer.tobytes())

        files = {'media': ('frame.jpg', image_file, 'image/jpeg')}
        
        try:
            r = requests.post('https://api.sightengine.com/1.0/check.json', 
                            files=files, 
                            data=params)
            
            output = r.json()
            ai_generated_score = output["type"]["ai_generated"]
            return ai_generated_score > 0.5
        except Exception as e:
            print(f"Error making API request: {e}")
    else:
        print("Failed to read frame from video")
    return False

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
    is_AI = filter_AI_video(
        video_url="https://pub-a55bd0dbae3c4afd86bd066961ab7d1e.r2.dev/test_10secs.mov",
        start_time=1,
        end_time=5,
        fps=24
    )
    print(is_AI)

