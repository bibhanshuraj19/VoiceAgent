from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Tuple
from zoneinfo import ZoneInfo


_TZ = ZoneInfo(os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Kolkata"))


_CREATE_OK = {
    "en-IN": "Done. I've added {title} on {date} at {time}.",
    "hi-IN": "हो गया। मैंने {title} को {date} को {time} बजे जोड़ दिया।",
}

_UPDATE_OK = {
    "en-IN": "Updated. {title} is now on {date} at {time}.",
    "hi-IN": "बदल दिया। {title} अब {date} को {time} बजे है।",
}

_DELETE_OK = {
    "en-IN": "Done. I've cancelled that appointment.",
    "hi-IN": "हो गया। मैंने वह अपॉइंटमेंट रद्द कर दिया।",
}

_ERROR = {
    "en-IN": "Sorry, that didn't go through. {reason}",
    "hi-IN": "माफ़ कीजिए, वह नहीं हो पाया। {reason}",
}

_UNKNOWN = {
    "en-IN": "Sorry, I couldn't complete that action.",
    "hi-IN": "माफ़ कीजिए, मैं वह काम पूरा नहीं कर सका।",
}


def _pick(table: Dict[str, str], language_code: str) -> str:
    return table.get(language_code) or table["en-IN"]


def _format_time(event: dict) -> Tuple[str, str]:
    start = event.get("start") or {}
    iso = start.get("dateTime") or ""
    if not iso:
        return ("", "")
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(_TZ)
    except ValueError:
        return ("", "")
    return (dt.strftime("%d %B"), dt.strftime("%I:%M %p").lstrip("0"))


def confirm(tool_name: str, result_json: str, language_code: str) -> str:
    try:
        result = json.loads(result_json)
    except (TypeError, json.JSONDecodeError):
        return _pick(_UNKNOWN, language_code)

    if not result.get("ok"):
        reason = (result.get("error") or "").strip()
        template = _pick(_ERROR, language_code)
        return template.format(reason=reason) if reason else _pick(_UNKNOWN, language_code)

    title = result.get("summary") or "the appointment"
    date, time = _format_time(result)

    if tool_name == "create_calendar_event":
        return _pick(_CREATE_OK, language_code).format(
            title=title,
            date=date or "today",
            time=time or "the scheduled time",
        )
    if tool_name == "update_calendar_event":
        return _pick(_UPDATE_OK, language_code).format(
            title=title,
            date=date or "the new date",
            time=time or "the new time",
        )
    if tool_name == "delete_calendar_event":
        return _pick(_DELETE_OK, language_code)
    return _pick(_UNKNOWN, language_code)
