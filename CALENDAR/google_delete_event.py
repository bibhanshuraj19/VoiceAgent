import os
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()


def _get_service():
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
    )
    creds.refresh(Request())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def delete_calendar_event(args):
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return {"ok": False, "error": "event_id is required"}

    try:
        service = _get_service()
        service.events().delete(
            calendarId="primary", eventId=event_id, sendUpdates="all"
        ).execute()
        return {"ok": True, "event_id": event_id, "message": "Event cancelled successfully"}
    except HttpError as e:
        return {"ok": False, "error": f"Google API error: {e.reason or e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
