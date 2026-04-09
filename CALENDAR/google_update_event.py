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


def update_calendar_event(args):
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return {"ok": False, "error": "event_id is required"}

    try:
        service = _get_service()
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        title = (args.get("title") or "").strip()
        if title:
            event["summary"] = title

        description = (args.get("description") or "").strip()
        if description:
            event["description"] = description

        start_iso = (args.get("start_iso") or "").strip()
        if start_iso:
            start = _parse_dt(start_iso)
            event["start"] = {"dateTime": start.isoformat(), "timeZone": TZ_NAME}

            end_iso = (args.get("end_iso") or "").strip()
            if end_iso:
                end = _parse_dt(end_iso)
            else:
                end = start + timedelta(minutes=int(args.get("duration_minutes") or 30))
            event["end"] = {"dateTime": end.isoformat(), "timeZone": TZ_NAME}

        elif end_iso := (args.get("end_iso") or "").strip():
            end = _parse_dt(end_iso)
            event["end"] = {"dateTime": end.isoformat(), "timeZone": TZ_NAME}

        updated = service.events().update(
            calendarId="primary", eventId=event_id, body=event, sendUpdates="all"
        ).execute()
        return {
            "ok": True,
            "event_id": updated["id"],
            "html_link": updated.get("htmlLink"),
            "summary": updated.get("summary"),
            "start": updated.get("start"),
            "end": updated.get("end"),
        }
    except HttpError as e:
        return {"ok": False, "error": f"Google API error: {e.reason or e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
