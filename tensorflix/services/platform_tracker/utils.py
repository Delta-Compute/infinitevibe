import requests
import json
import cv2
from io import BytesIO
from apify_client import ApifyClient
import time
import os

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
def download_video(video_url, output_filename="video.mp4", quality="360p", api_key="apify_api_rcJsLLEKZualTGzmFGGmAefnL9ETl03lKuS2"):
    """
    Download a video using Apify client.
    
    Args:
        video_url (str): The Video URL to download
        output_filename (str): The filename to save the video as (default: "video.mp4")
        quality (str): The video quality to download (default: "360p")
        api_key (str): Apify API key
    
    Returns:
        str: The filename of the downloaded video if successful, None otherwise
    """
    client = ApifyClient(api_key)
    start = time.time()
    
    run_input = {
        "link": video_url,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
        },
        "quality": quality,
    }

    try:
        # Run the Actor and wait for it to finish
        run = client.actor("iZbsVYT4VfdMxoIPL").call(run_input=run_input)

        # Fetch and print Actor results from the run's dataset (if there are any)
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            lst_response = item["result"]["medias"]
            
            for response in lst_response:
                if (response["type"] == "video" and 
                    f"mp4 ({quality})" in response["quality"] and 
                    response["width"] == 360 and 
                    "googlevideo.com" in response["url"]):
                    
                    print("Item found:", item)
                    print("Download URL:", response["url"])
                    print("*" * 100)
                    
                    # Download the video
                    video_downloaded = requests.get(response["url"])
                    with open(output_filename, "wb") as f:
                        f.write(video_downloaded.content)
                    
                    print(f"Video downloaded successfully as {output_filename}")
                    print(f"Download completed in {time.time() - start:.2f} seconds")
                    return output_filename
        
        print("No suitable video found with the specified criteria")
        return None
        
    except Exception as e:
        print(f"Error downloading video: {str(e)}")
        return None

if __name__ == "__main__":
    is_AI = filter_AI_video(
        video_url="https://pub-a55bd0dbae3c4afd86bd066961ab7d1e.r2.dev/test_10secs.mov",
        start_time=1,
        end_time=5,
        fps=24
    )
    print(is_AI)

