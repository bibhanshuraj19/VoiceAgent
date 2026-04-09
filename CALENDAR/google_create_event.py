import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

TZ_NAME = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Kolkata")
TZ = ZoneInfo(TZ_NAME)


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


def _parse_dt(iso_str):
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def create_calendar_event(args):
    title = (args.get("title") or "").strip()
    start_iso = (args.get("start_iso") or "").strip()

    if not title or not start_iso:
        return {"ok": False, "error": "title and start_iso are required"}

    start = _parse_dt(start_iso)

    end_iso = (args.get("end_iso") or "").strip()
    if end_iso:
        end = _parse_dt(end_iso)
    else:
        end = start + timedelta(minutes=int(args.get("duration_minutes") or 30))

    if end <= start:
        return {"ok": False, "error": "end time must be after start time"}

    event_body = {
        "summary": title,
        "start": {"dateTime": start.isoformat(), "timeZone": TZ_NAME},
        "end": {"dateTime": end.isoformat(), "timeZone": TZ_NAME},
    }

    description = (args.get("description") or "").strip()
    if description:
        event_body["description"] = description

    attendees = args.get("attendees")
    if attendees:
        event_body["attendees"] = [{"email": e} for e in attendees]

    try:
        service = _get_service()
        created = service.events().insert(
            calendarId="primary", body=event_body, sendUpdates="all"
        ).execute()
        return {
            "ok": True,
            "event_id": created["id"],
            "html_link": created.get("htmlLink"),
            "summary": created.get("summary"),
            "start": created.get("start"),
            "end": created.get("end"),
        }
    except HttpError as e:
        return {"ok": False, "error": f"Google API error: {e.reason or e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
