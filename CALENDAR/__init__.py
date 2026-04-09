import json
from CALENDAR.google_create_event import create_calendar_event
from CALENDAR.google_update_event import update_calendar_event
from CALENDAR.google_delete_event import delete_calendar_event
from CALENDAR.google_calendar_tools import ALL_FUNCTIONS

_DISPATCH = {
    "create_calendar_event": create_calendar_event,
    "update_calendar_event": update_calendar_event,
    "delete_calendar_event": delete_calendar_event,
}


def dispatch_function(name, arguments_json):
    fn = _DISPATCH.get(name)
    if not fn:
        return json.dumps({"ok": False, "error": f"Unknown function: {name}"})

    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"ok": False, "error": f"Invalid JSON: {e}"})

    return json.dumps(fn(args))
