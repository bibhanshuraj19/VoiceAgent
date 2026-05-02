import os
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
from CALENDAR.google_calendar_credentials import get_calendar_service
from CALENDAR.google_event_lookup import resolve_event

load_dotenv()

def delete_calendar_event(args):
    try:
        service = get_calendar_service()
        event, error = resolve_event(service, args)
        if event is None:
            return {"ok": False, "error": error or "Could not find that appointment."}
        event_id = (event.get("id") or "").strip()
        if not event_id:
            return {"ok": False, "error": "Resolved event is missing an id."}
        service.events().delete(
            calendarId="primary", eventId=event_id, sendUpdates="all"
        ).execute()
        return {
            "ok": True,
            "event_id": event_id,
            "message": "Event cancelled successfully",
            "summary": event.get("summary"),
            "start": event.get("start"),
            "end": event.get("end"),
        }
    except HttpError as e:
        return {"ok": False, "error": f"Google API error: {e.reason or e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
