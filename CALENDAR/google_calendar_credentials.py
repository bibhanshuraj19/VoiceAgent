import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def get_calendar_service():
    refresh_token = (os.getenv("GOOGLE_REFRESH_TOKEN") or "").strip()
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    missing = [
        name
        for name, value in (
            ("GOOGLE_REFRESH_TOKEN", refresh_token),
            ("GOOGLE_CLIENT_ID", client_id),
            ("GOOGLE_CLIENT_SECRET", client_secret),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing Google Calendar credentials: {', '.join(missing)}")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
    )
    creds.refresh(Request())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)
