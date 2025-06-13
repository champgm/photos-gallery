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
import time

# The scope needed to access Google Photos Picker API
SCOPES = ["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"]
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


def create_picker_session(creds):
    """Create a new Google Photos Picker session and return session info."""
    session = SessionManager.get_session()
    
    response = session.post(
        "https://photospicker.googleapis.com/v1/sessions",
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json"
        },
        json={}  # Empty body - basic session creation
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to create picker session: {response.status_code} - {response.text}")
    
    session_data = response.json()
    return session_data


def poll_session(creds, session_id):
    """Poll the session until user has completed media selection."""
    session = SessionManager.get_session()
    
    while True:
        response = session.get(
            f"https://photospicker.googleapis.com/v1/sessions/{session_id}",
            headers={
                "Authorization": f"Bearer {creds.token}"
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to poll session: {response.status_code} - {response.text}")
        
        session_data = response.json()
        
        # Check if user has completed selection
        if session_data.get("mediaItemsSet", False):
            print("User has completed media selection!")
            return session_data
        
        # Get polling configuration
        polling_config = session_data.get("pollingConfig", {})
        poll_interval = polling_config.get("pollInterval", "10s")
        timeout_in = polling_config.get("timeoutIn", "300s")
        
        # Debug: show what we received
        print(f"Debug - polling config: {polling_config}")
        print(f"Debug - poll_interval: {poll_interval} (type: {type(poll_interval)})")
        print(f"Debug - timeout_in: {timeout_in} (type: {type(timeout_in)})")
        
        # Parse interval - handle both "10s" format and plain number format
        try:
            if isinstance(poll_interval, str) and poll_interval.endswith('s'):
                interval_seconds = int(poll_interval.rstrip('s'))
            else:
                interval_seconds = int(float(str(poll_interval)))
        except (ValueError, TypeError):
            interval_seconds = 10  # Default fallback
        
        # Parse timeout - handle both "300s" format and plain number format
        try:
            if isinstance(timeout_in, str) and timeout_in.endswith('s'):
                timeout_seconds = int(timeout_in.rstrip('s'))
            else:
                timeout_seconds = int(float(str(timeout_in)))
        except (ValueError, TypeError):
            timeout_seconds = 300  # Default fallback
        
        print(f"Waiting for user selection... polling every {interval_seconds} seconds")
        print(f"Session will timeout in {timeout_seconds} seconds")
        
        time.sleep(interval_seconds)


def list_selected_media_items(creds, session_id):
    """List all media items selected by the user."""
    session = SessionManager.get_session()
    items = []
    next_page_token = None
    
    while True:
        params = {"sessionId": session_id}
        if next_page_token:
            params["pageToken"] = next_page_token
        
        response = session.get(
            "https://photospicker.googleapis.com/v1/mediaItems",
            headers={
                "Authorization": f"Bearer {creds.token}"
            },
            params=params
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to list media items: {response.status_code} - {response.text}")
        
        data = response.json()
        
        # Add items from this page
        page_items = data.get("pickedMediaItems", [])
        items.extend(page_items)
        
        print(f"Found {len(page_items)} items on this page, {len(items)} total so far")
        
        # Check for next page
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
    
    print(f"Total items selected: {len(items)}")
    return items


def file_does_not_exist(file_path: str):
    return not os.path.exists(file_path)


def download_item(creds, download_url, local_path):
    print(f"Downloading {local_path}")
    session = SessionManager.get_session()
    
    # For Picker API, we need to include authorization header
    response = session.get(
        download_url,
        headers={
            "Authorization": f"Bearer {creds.token}"
        }
    )
    
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


def get_filename_from_media_item(item):
    """Extract filename from picked media item."""
    # Try to get filename from mediaFile if available
    media_file = item.get("mediaFile", {})
    filename = media_file.get("filename")
    
    if not filename:
        # Fallback: use the ID as filename with appropriate extension based on mimeType
        mime_type = media_file.get("mimeType", "")
        item_id = item.get("id", "unknown")
        
        if mime_type.startswith("image/"):
            if "jpeg" in mime_type or "jpg" in mime_type:
                extension = ".jpg"
            elif "png" in mime_type:
                extension = ".png"
            elif "gif" in mime_type:
                extension = ".gif"
            else:
                extension = ".jpg"  # default for images
        elif mime_type.startswith("video/"):
            if "mp4" in mime_type:
                extension = ".mp4"
            elif "mov" in mime_type:
                extension = ".mov"
            elif "avi" in mime_type:
                extension = ".avi"
            else:
                extension = ".mp4"  # default for videos
        else:
            extension = ".bin"  # unknown type
        
        filename = f"{item_id}{extension}"
    
    return filename


def download_selected_media(
    creds,
    session_id: str,
    image_dir: str,
    image_thumbnail_dir: str,
    video_dir: str,
    video_thumbnail_dir: str,
):
    """Download all media items selected by the user."""
    
    # Create directories if they don't exist
    for directory in [image_dir, image_thumbnail_dir, video_dir, video_thumbnail_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)
    
    # Get selected media items
    items = list_selected_media_items(creds, session_id)
    
    for item in items:
        media_file = item.get("mediaFile", {})
        base_url = media_file.get("baseUrl")
        mime_type = media_file.get("mimeType", "")
        filename = get_filename_from_media_item(item)
        
        if not base_url:
            print(f"Warning: No baseUrl found for item {item.get('id', 'unknown')}")
            continue
        
        # Determine file path based on media type
        if mime_type.startswith("image"):
            file_path = f"{image_dir}/{filename}"
            thumbnail_path = f"{image_thumbnail_dir}/{filename}"
        elif mime_type.startswith("video"):
            file_path = f"{video_dir}/{filename}"
            thumbnail_path = f"{video_thumbnail_dir}/{filename}.jpg"  # video thumbnails are typically JPG
        else:
            print(f"Warning: Unknown media type {mime_type} for item {item.get('id', 'unknown')}")
            continue
        
        # Create metadata file path
        meta_file_path = f"{file_path}.meta.json"
        
        # Save metadata
        if file_does_not_exist(meta_file_path):
            write_metadata(item, meta_file_path)
        else:
            print(f"Skipped {meta_file_path}")
        
        # Download full resolution media
        if file_does_not_exist(file_path):
            if mime_type.startswith("image"):
                download_url = f"{base_url}=d"  # =d for full resolution image
            elif mime_type.startswith("video"):
                download_url = f"{base_url}=dv"  # =dv for video download
            else:
                download_url = base_url
            
            download_item(creds, download_url, file_path)
        else:
            print(f"Skipped {file_path}")
        
        # Download thumbnail
        if file_does_not_exist(thumbnail_path):
            if mime_type.startswith("image"):
                thumbnail_url = f"{base_url}=w640-h640"
            elif mime_type.startswith("video"):
                thumbnail_url = f"{base_url}=w640-h640"  # Video thumbnail
            else:
                thumbnail_url = f"{base_url}=w640-h640"
            
            download_item(creds, thumbnail_url, thumbnail_path)
        else:
            print(f"Skipped {thumbnail_path}")


def cleanup_session(creds, session_id):
    """Clean up the session by deleting it."""
    session = SessionManager.get_session()
    
    response = session.delete(
        f"https://photospicker.googleapis.com/v1/sessions/{session_id}",
        headers={
            "Authorization": f"Bearer {creds.token}"
        }
    )
    
    if response.status_code == 200:
        print("Session cleaned up successfully")
    else:
        print(f"Warning: Failed to cleanup session: {response.status_code}")


@click.command()
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
    image_dir: str,
    image_thumbnail_dir: str,
    video_dir: str,
    video_thumbnail_dir: str,
):
    """
    Download photos and videos from Google Photos using the Picker API.
    
    This tool uses the Google Photos Picker API which requires user interaction
    to select media items. The process involves:
    1. Creating a picker session
    2. Opening the picker URL in a browser
    3. User selects photos/videos
    4. Downloading the selected items
    """
    print("Starting Google Photos Picker download process...")
    
    # Authenticate
    creds = authenticate()
    print("Authentication successful!")
    
    # Create picker session
    print("Creating picker session...")
    session_data = create_picker_session(creds)
    session_id = session_data["id"]
    picker_uri = session_data["pickerUri"]
    
    print("\n" + "="*60)
    print("IMPORTANT: Please open the following URL in your browser:")
    print(f"\n{picker_uri}\n")
    print("Select the photos and videos you want to download.")
    print("Click 'Done' when you have finished selecting.")
    print("="*60 + "\n")
    
    # Poll session until user completes selection
    try:
        print("Starting to poll for user selection...")
        poll_session(creds, session_id)
        
        # Download selected media
        print("User selection complete! Starting download...")
        download_selected_media(
            creds, session_id, image_dir, image_thumbnail_dir, video_dir, video_thumbnail_dir
        )
        
        print("Download completed successfully!")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up session
        print("Cleaning up session...")
        cleanup_session(creds, session_id)


if __name__ == "__main__":
    main()
