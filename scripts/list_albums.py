from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle
import os

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


def list_albums(service):
    try:
        results = (
            service.albums()
            .list(
                pageSize=50, excludeNonAppCreatedData=False  # Adjust pageSize as needed
            )
            .execute()
        )
        albums = results.get("albums", [])
        return albums
    except Exception as e:
        print(f"Error listing albums: {e}")
        return []


def main():
    creds = authenticate()
    service = build("photoslibrary", "v1", credentials=creds, static_discovery=False)
    albums = list_albums(service)

    if not albums:
        print("No albums found.")
    else:
        for album in albums:
            print(f"Album name: {album['title']}, Album ID: {album['id']}")


if __name__ == "__main__":
    main()
