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


def list_album_photos(service, album_id):
    request_body = {
        "albumId": album_id,
        "pageSize": 100,  # Max is 100
    }
    items = []  # Initialize an empty list to store all items
    while True:
        response = service.mediaItems().search(body=request_body).execute()
        items.extend(response.get("mediaItems", []))

        # Check for nextPageToken in the response and update request_body to include it
        if 'nextPageToken' in response:
            print("Fetching next page of results...")
            request_body['pageToken'] = response['nextPageToken']
        else:
            break  # Exit loop if no more pages

    if len(items) == 0:
        print("No items found in album.")
    else:
        print(f"Found {len(items)} items in album:")
        for item in items:
            print(f"Photo {item['filename']} found in album.")
    return items



def should_download_photo(photo_file_path: str, meta_file_path: str):
    if not os.path.exists(photo_file_path):
        return True
    if not os.path.exists(meta_file_path):
        return True
    return False


def download_photo(photo_url, local_path):
    session = requests.Session()
    retries = Retry(total=5,  # Total number of retries
                    backoff_factor=1,  # Exponential backoff factor
                    status_forcelist=[500, 502, 503, 504],  # Status codes to force a retry on
                    allowed_methods=frozenset(['GET', 'POST']))  # HTTP methods to retry
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)

    response = session.get(photo_url)
    if response.status_code == 200:
        with open(local_path, "wb") as f:
            f.write(response.content)
    else:
        print(f"Failed to download {photo_url}, status code: {response.status_code}")



def write_metadata(metadata, local_meta_path):
    with open(local_meta_path, "w") as json_file:
        json.dump(metadata, json_file, indent=2)


def download_album(album_id: str, destination_dir: str):
    creds = authenticate()
    service = build("photoslibrary", "v1", credentials=creds, static_discovery=False)
    photos = list_album_photos(service, album_id)

    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    for photo in photos:
        base_url = photo["baseUrl"]
        download_url = f"{base_url}=d"  # Download URL for full resolution
        photo_file_path = os.path.join(destination_dir, photo["filename"])
        meta_file_path = f"{photo_file_path}.meta.json"
        if should_download_photo(photo_file_path, meta_file_path):
            photo_metadata = service.mediaItems().get(mediaItemId=photo["id"]).execute()
            download_photo(download_url, photo_file_path)
            write_metadata(photo_metadata, meta_file_path)
            print(f'Downloaded {photo["filename"]}')
        else:
            print(f'Skipped {photo["filename"]}')


@click.command()
@click.option("--album-id", required=True, help="ID for the album to download")
@click.option(
    "--destination_dir",
    required=True,
    default="img_down",
    help="Destination directory of images",
)
def main(album_id: str, destination_dir: str):
    download_album(album_id, destination_dir)


if __name__ == "__main__":
    main()
