import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
from CALENDAR.google_calendar_credentials import get_calendar_service
from CALENDAR.google_event_lookup import resolve_event

load_dotenv()

TZ_NAME = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Kolkata")
TZ = ZoneInfo(TZ_NAME)


def _parse_dt(iso_str):
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def update_calendar_event(args):
    try:
        service = get_calendar_service()
        event, error = resolve_event(service, args)
        if event is None:
            return {"ok": False, "error": error or "Could not find that appointment."}
        event_id = (event.get("id") or "").strip()
        if not event_id:
            return {"ok": False, "error": "Resolved event is missing an id."}

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

        start_info = event.get("start") or {}
        end_info = event.get("end") or {}
        start_value = (start_info.get("dateTime") or "").strip()
        end_value = (end_info.get("dateTime") or "").strip()
        if start_value and end_value:
            start_dt = _parse_dt(start_value)
            end_dt = _parse_dt(end_value)
            if end_dt <= start_dt:
                return {"ok": False, "error": "end time must be after start time"}

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
