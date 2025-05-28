from pydantic import BaseModel
import httpx
import json


class YoutubeSubmission(BaseModel):
    video_id: str
    task_id: str


class PeerMetadata(BaseModel):
    uid: str
    hotkey: str
    commit: str
    submissions: list[YoutubeSubmission] = []

    async def update_submissions(self):
        username, gist_id = self.commit.split(":")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://gist.githubusercontent.com/{username}/{gist_id}/raw",
            )
            gist_data = json.loads(response.text)
            print(gist_data)
            self.submissions = [
                YoutubeSubmission(task_id=item[0], video_id=item[1])
                for item in gist_data["submissions"]
            ]


if __name__ == "__main__":
    import asyncio

    commit = "toilaluan:671296b3465daf4fcafafcb438f67f64"

    async def main():
        peer_metadata = PeerMetadata(commit=commit, uid="0")
        await peer_metadata.update_submissions()
        print(peer_metadata)

    asyncio.run(main())
