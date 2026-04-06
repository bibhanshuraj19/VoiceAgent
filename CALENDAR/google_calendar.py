from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_credentials() -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def create_calendar_event(args: dict[str, Any]) -> dict[str, Any]:
    title = (args.get("title") or "").strip()
    start_iso = (args.get("start_iso") or "").strip()

    if not title or not start_iso:
        return {"ok": False, "error": "title and start_iso are required"}

    tz_name = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "UTC")
    tz = ZoneInfo(tz_name)

    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    start = start if start.tzinfo else start.replace(tzinfo=tz)

    end_iso = (args.get("end_iso") or "").strip()
    if end_iso:
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        end = end if end.tzinfo else end.replace(tzinfo=tz)
    else:
        end = start + timedelta(minutes=int(args.get("duration_minutes") or 60))

    if end <= start:
        return {"ok": False, "error": "end time must be after start time"}

    event_body: dict[str, Any] = {
        "summary": title,
        "start": {"dateTime": start.isoformat(), "timeZone": tz_name},
        "end": {"dateTime": end.isoformat(), "timeZone": tz_name},
    }

    if description := (args.get("description") or "").strip():
        event_body["description"] = description

    try:
        service = build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)
        created = service.events().insert(calendarId="primary", body=event_body).execute()
        return {
            "ok": True,
            "event_id": created.get("id"),
            "html_link": created.get("htmlLink"),
            "summary": created.get("summary"),
            "start": created.get("start"),
            "end": created.get("end"),
        }

    except HttpError as exc:
        return {"ok": False, "error": f"Google Calendar API error: {exc.reason or exc}"}

    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def dispatch_function(name: str, arguments_json: str) -> str:
    if name != "create_calendar_event":
        return json.dumps({"ok": False, "error": f"Unknown function: {name}"})

    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as exc:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {exc}"})

    return json.dumps(create_calendar_event(args))