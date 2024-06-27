from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import click
import json
import os
import pickle
import requests

# The scope needed to access Google Photos
SCOPES = ["https://www.googleapis.com/auth/photoslibrary.readonly"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"


class SessionManager:
    _session = None  # Private class variable to hold the singleton session

    @classmethod
    def get_session(cls):
        if cls._session is None:
            session = requests.Session()
            retries = Retry(
                total=5,  # Total number of retries
                backoff_factor=3,  # Exponential
                status_forcelist=[
                    500,
                    502,
                    503,
                    504,
                ],  # Status codes to retry
                allowed_methods=frozenset(["GET", "POST"]),
            )  # HTTP methods to retry
            adapter = HTTPAdapter(max_retries=retries)
            session.mount("https://", adapter)
            cls._session = session  # Initialize the session if it hasn't been already
        return cls._session


def authenticate():
    creds = None
    # Load the saved credentials if they exist.
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    # If credentials are not valid or are expired, re-authenticate.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run.
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return creds


def list_album_items(service, album_id):
    request_body = {
        "albumId": album_id,
        "pageSize": 100,  # Max is 100
    }
    items = []  # Initialize an empty list to store all items
    while True:
        response = service.mediaItems().search(body=request_body).execute()
        items.extend(response.get("mediaItems", []))

        # Check for nextPageToken in the response and update request_body to include it
        if "nextPageToken" in response:
            print("Fetching next page of results...")
            request_body["pageToken"] = response["nextPageToken"]
        else:
            break  # Exit loop if no more pages

    if len(items) == 0:
        print("No items found in album.")
    else:
        print(f"Found {len(items)} items in album:")
        for item in items:
            print(f"Item {item['filename']} found in album.")
    return items


def file_does_not_exist(file_path: str):
    return not os.path.exists(file_path)


def download_item(download_url, local_path):
    print(f"Downloading {local_path}")
    session = SessionManager.get_session()
    response = session.get(download_url)
    if response.status_code == 200:
        with open(local_path, "wb") as f:
            f.write(response.content)
            print(f"Downloaded {local_path}")
    else:
        print(f"Failed to download {download_url}, status code: {response.status_code}")
        raise Exception(
            f"Failed to download {download_url}, status code: {response.status_code}"
        )


def write_metadata(metadata, local_meta_path):
    with open(local_meta_path, "w") as json_file:
        json.dump(metadata, json_file, indent=2)


def download_album(
    album_id: str,
    image_dir: str,
    image_thumbnail_dir: str,
    video_dir: str,
    video_thumbnail_dir: str,
):
    creds = authenticate()
    service = build("photoslibrary", "v1", credentials=creds, static_discovery=False)
    items = list_album_items(service, album_id)

    if not os.path.exists(image_dir):
        os.makedirs(image_dir)
    if not os.path.exists(video_dir):
        os.makedirs(video_dir)
    if not os.path.exists(video_thumbnail_dir):
        os.makedirs(video_thumbnail_dir)

    for item in items:
        base_url = item["baseUrl"]
        file_path = (
            f"{image_dir}/{item['filename']}"
            if item["mimeType"].startswith("image")
            else f"{video_dir}/{item['filename']}"
        )
        meta_file_path = f"{file_path}.meta.json"

        # Grab metadata
        item_metadata = None
        if file_does_not_exist(meta_file_path):
            item_metadata = service.mediaItems().get(mediaItemId=item["id"]).execute()
            write_metadata(item_metadata, meta_file_path)
        else:
            item_metadata = json.load(open(meta_file_path))
            print(f"Skipped {meta_file_path}")

        if item_metadata is not None and item_metadata["mimeType"].startswith("image"):
            # Download full resolution image
            if file_does_not_exist(file_path):
                download_url = f"{base_url}=d"  # =d for full resolution
                download_item(download_url, file_path)
            else:
                print(f"Skipped {file_path}")
            # Download thumbnail
            thumbnail_path = f"{image_thumbnail_dir}/{item['filename']}"
            if file_does_not_exist(thumbnail_path):
                thumbnail_url = f"{base_url}=w640-h640"
                download_item(thumbnail_url, thumbnail_path)
            else:
                print(f"Skipped {thumbnail_path}")
        elif item_metadata is not None and item_metadata["mimeType"].startswith("video"):
            # Download video
            if file_does_not_exist(file_path):
                download_url = f"{base_url}=dv"  # =dv for bytes
                download_item(download_url, file_path)
            else:
                print(f"Skipped {file_path}")
            # Download thumbnail
            thumbnail_path = f"{video_thumbnail_dir}/{item['filename']}.jpg"
            if file_does_not_exist(thumbnail_path):
                thumbnail_url = f"{base_url}=d-w640-h640"
                download_item(thumbnail_url, thumbnail_path)
            else:
                print(f"Skipped {thumbnail_path}")


@click.command()
@click.option("--album-id", required=True, help="ID for the album to download")
@click.option(
    "--image_dir",
    required=True,
    default="images",
    help="Destination directory for images",
)
@click.option(
    "--image_thumbnail_dir",
    required=True,
    default="thumbnail",
    help="Destination directory for image thumbnails",
)
@click.option(
    "--video_dir",
    required=True,
    default="videos",
    help="Destination directory for videos",
)
@click.option(
    "--video_thumbnail_dir",
    required=True,
    default="video_thumbnail",
    help="Destination directory for video thumbnails",
)
def main(
    album_id: str,
    image_dir: str,
    image_thumbnail_dir: str,
    video_dir: str,
    video_thumbnail_dir: str,
):
    download_album(
        album_id, image_dir, image_thumbnail_dir, video_dir, video_thumbnail_dir
    )


if __name__ == "__main__":
    main()
