"""OpenAI-style tool schemas for calendar (no Deepgram SDK)."""

CREATE_CALENDAR_EVENT = {
    "type": "function",
    "function": {
        "name": "create_calendar_event",
        "description": "Create a Google Calendar appointment when the user schedules or books.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_iso": {"type": "string", "description": "ISO 8601 with timezone"},
                "end_iso": {"type": "string"},
                "duration_minutes": {"type": "integer"},
                "description": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "start_iso"],
        },
    },
}

UPDATE_CALENDAR_EVENT = {
    "type": "function",
    "function": {
        "name": "update_calendar_event",
        "description": "Reschedule or modify an existing calendar event.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "title": {"type": "string"},
                "start_iso": {"type": "string"},
                "target_date": {"type": "string", "description": "ISO date like YYYY-MM-DD to help identify the event"},
                "end_iso": {"type": "string"},
                "duration_minutes": {"type": "integer"},
                "description": {"type": "string"},
            },
            "required": [],
        },
    },
}

DELETE_CALENDAR_EVENT = {
    "type": "function",
    "function": {
        "name": "delete_calendar_event",
        "description": "Cancel or delete a calendar event.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "title": {"type": "string"},
                "target_date": {"type": "string", "description": "ISO date like YYYY-MM-DD to help identify the event"},
            },
            "required": [],
        },
    },
}

ALL_FUNCTIONS = [CREATE_CALENDAR_EVENT, UPDATE_CALENDAR_EVENT, DELETE_CALENDAR_EVENT]
