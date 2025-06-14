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
    
    return response.json()


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
        
        # Parse interval - handle both string and number formats
        try:
            if isinstance(poll_interval, str) and poll_interval.endswith('s'):
                interval_seconds = int(poll_interval.rstrip('s'))
            else:
                interval_seconds = int(float(str(poll_interval)))
        except (ValueError, TypeError):
            interval_seconds = 10  # Default fallback
        
        print(f"Waiting for user selection... polling every {interval_seconds} seconds")
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
        page_items = data.get("mediaItems", [])
        items.extend(page_items)
        
        print(f"Found {len(page_items)} items on this page, {len(items)} total so far")
        
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
    """
    Write metadata, transforming Picker API structure to Library API structure
    for backward compatibility with generate_photos_gallery.py
    """
    # Transform Picker API structure to Library API structure
    media_file = metadata.get("mediaFile", {})
    media_file_metadata = media_file.get("mediaFileMetadata", {})
    
    # Create Library API compatible structure
    transformed_metadata = {
        "full": metadata,
        "id": metadata.get("id"),
        "filename": media_file.get("filename") or metadata.get("filename"),
        "mimeType": media_file.get("mimeType"),
        "baseUrl": media_file.get("baseUrl"),
        # Add missing required fields with reasonable defaults
        "productUrl": f"https://photos.google.com/lr/photo/{metadata.get('id', '')}",
        "mediaMetadata": {
            "creationTime": metadata.get("createTime", ""),
            "width": str(media_file_metadata.get("width", "0")),
            "height": str(media_file_metadata.get("height", "0")),
            "photo": {},
            "video": {},
        }
    }
    
    # Keep any additional fields from the original metadata
    for key, value in metadata.items():
        if key not in transformed_metadata and key != "mediaFile":
            transformed_metadata[key] = value
    
    with open(local_meta_path, "w") as json_file:
        json.dump(transformed_metadata, json_file, indent=2)


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
        
        # Get filename - try mediaFile first, then item directly for compatibility
        filename = media_file.get("filename") or item.get("filename")
        if not filename:
            # Fallback: use ID with extension
            item_id = item.get("id", "unknown")
            ext = ".jpg" if mime_type.startswith("image") else ".mp4" if mime_type.startswith("video") else ".bin"
            filename = f"{item_id}{ext}"
            print(f"Warning: No filename for item {item_id}, would have used \"{filename}\"")
            continue
        
        if not base_url:
            print(f"Warning: No baseUrl found for item {filename}")
            continue
        
        # Determine file paths
        if mime_type.startswith("image"):
            file_path = f"{image_dir}/{filename}"
            thumbnail_path = f"{image_thumbnail_dir}/{filename}"
        elif mime_type.startswith("video"):
            file_path = f"{video_dir}/{filename}"
            thumbnail_path = f"{video_thumbnail_dir}/{filename}.jpg"
        else:
            print(f"Warning: Unknown media type {mime_type} for {filename}")
            continue
        
        meta_file_path = f"{file_path}.meta.json"
        
        # Save metadata
        if file_does_not_exist(meta_file_path):
            write_metadata(item, meta_file_path)
        else:
            print(f"Skipped {meta_file_path}")
        
        # Download full resolution media
        if file_does_not_exist(file_path):
            if mime_type.startswith("image"):
                download_url = f"{base_url}=d"  # =d for full resolution
            elif mime_type.startswith("video"):
                download_url = f"{base_url}=dv"  # =dv for video download
            else:
                download_url = f"{base_url}=d"
            
            download_item(creds, download_url, file_path)
        else:
            print(f"Skipped {file_path}")
        
        # Download thumbnail
        if file_does_not_exist(thumbnail_path):
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
        poll_session(creds, session_id)
        
        # Download selected media
        download_selected_media(
            creds, session_id, image_dir, image_thumbnail_dir, video_dir, video_thumbnail_dir
        )
        
        print("Download completed successfully!")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        
    finally:
        # Clean up session
        cleanup_session(creds, session_id)


if __name__ == "__main__":
    main()
