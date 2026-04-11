import os
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
from CALENDAR.google_calendar_credentials import get_calendar_service

load_dotenv()

def delete_calendar_event(args):
    event_id = (args.get("event_id") or "").strip()
    if not event_id:
        return {"ok": False, "error": "event_id is required"}

    try:
        service = get_calendar_service()
        service.events().delete(
            calendarId="primary", eventId=event_id, sendUpdates="all"
        ).execute()
        return {"ok": True, "event_id": event_id, "message": "Event cancelled successfully"}
    except HttpError as e:
        return {"ok": False, "error": f"Google API error: {e.reason or e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
