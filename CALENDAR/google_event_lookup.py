import os
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo


TZ_NAME = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Kolkata")
TZ = ZoneInfo(TZ_NAME)
_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)


def resolve_event(service, args: dict) -> Tuple[Optional[dict], Optional[str]]:
    event_id = (args.get("event_id") or "").strip()
    if event_id:
        try:
            return service.events().get(calendarId="primary", eventId=event_id).execute(), None
        except Exception as exc:
            return None, str(exc)

    title = (args.get("title") or args.get("summary") or "").strip()
    if not title:
        return None, "event_id or title is required"

    target_date = _extract_target_date(args)
    time_min, time_max = _window_for_date(target_date)

    response = service.events().list(
        calendarId="primary",
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        q=title,
        maxResults=12,
    ).execute()
    items = response.get("items") or []
    if not items:
        return None, f"No calendar event matched '{title}'."

    picked = _pick_best_match(items, title=title, target_date=target_date)
    if picked is None:
        return None, f"No calendar event matched '{title}'."
    return picked, None


def _extract_target_date(args: dict) -> Optional[datetime]:
    raw_date = (args.get("target_date") or "").strip()
    if raw_date:
        try:
            dt = datetime.fromisoformat(raw_date)
            return dt if dt.tzinfo else dt.replace(tzinfo=TZ)
        except ValueError:
            try:
                return datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=TZ)
            except ValueError:
                return None

    start_iso = (args.get("start_iso") or "").strip()
    if not start_iso:
        return None
    try:
        dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def _window_for_date(target_date: Optional[datetime]) -> Tuple[datetime, datetime]:
    if target_date is None:
        start = datetime.now(TZ) - timedelta(days=30)
        end = datetime.now(TZ) + timedelta(days=180)
        return start, end

    day_start = target_date.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return day_start - timedelta(days=1), day_start + timedelta(days=2)


def _pick_best_match(items: list[dict], *, title: str, target_date: Optional[datetime]) -> Optional[dict]:
    wanted = _normalize(title)
    wanted_date = target_date.astimezone(TZ).date() if target_date is not None else None
    best: Optional[tuple[int, dict]] = None

    for item in items:
        summary = _normalize((item.get("summary") or "").strip())
        if not summary:
            continue

        score = 0
        if summary == wanted:
            score += 4
        elif wanted and wanted in summary:
            score += 2
        elif summary and summary in wanted:
            score += 1

        item_date = _event_start_date(item)
        if wanted_date is not None and item_date == wanted_date:
            score += 4
        elif wanted_date is None and item_date is not None:
            score += 1

        if best is None or score > best[0]:
            best = (score, item)

    if best is None or best[0] <= 0:
        return None
    return best[1]


def _event_start_date(event: dict) -> Optional[datetime.date]:
    start = event.get("start") or {}
    iso = (start.get("dateTime") or "").strip()
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    dt = dt if dt.tzinfo else dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ).date()


def _normalize(text: str) -> str:
    return _NON_WORD_RE.sub("", text.casefold())
