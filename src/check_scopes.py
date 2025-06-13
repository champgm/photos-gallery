#!/usr/bin/env python3
"""
inspect_token.py – show the OAuth scopes stored in token.pickle
"""
import pickle
import json
import sys
import urllib.request
import urllib.error

TOKEN_PATH = "token.pickle"   # change if yours lives elsewhere

def main():
    # 1. Load the pickled Credentials object
    try:
        with open(TOKEN_PATH, "rb") as fh:
            creds = pickle.load(fh)
    except FileNotFoundError:
        sys.exit(f"❌ Could not find {TOKEN_PATH}")

    # 2. Show the scopes that were granted when the file was created
    print("Local credentials say these scopes are allowed:")
    for s in (creds.scopes or []):
        print("  •", s)

    # 3. Ask Google’s tokeninfo endpoint (optional but authoritative)
    print("\nAsking Google tokeninfo…")
    url = f"https://oauth2.googleapis.com/tokeninfo?access_token={creds.token}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.load(resp)
        scopes_from_google = data.get("scope", "")
        print("Google says scopes are:")
        for s in scopes_from_google.split():
            print("  •", s)
        if scopes_from_google.strip() == "":
            print("(Token has expired or was revoked.)")
    except urllib.error.HTTPError as e:
        print("Could not query tokeninfo:", e)

if __name__ == "__main__":
    main()
