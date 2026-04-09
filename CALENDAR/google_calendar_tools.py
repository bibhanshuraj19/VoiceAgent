from deepgram.types.think_settings_v1functions_item import ThinkSettingsV1FunctionsItem

CREATE_CALENDAR_EVENT = ThinkSettingsV1FunctionsItem(
    name="create_calendar_event",
    description=(
        "Create an appointment on the user's Google Calendar when they ask to "
        "schedule, book, reserve, or add a meeting or appointment. "
        "start_iso must be ISO 8601 with date and time."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the event",
            },
            "start_iso": {
                "type": "string",
                "description": "Start time in ISO format (e.g. 2024-03-20T09:00:00)",
            },
            "end_iso": {
                "type": "string",
                "description": "End time in ISO format",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Duration in minutes when end_iso is not given, default 45",
            },
            "description": {
                "type": "string",
                "description": "Optional event notes",
            },
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Email addresses to invite",
            },
        },
        "required": ["title", "start_iso"],
    },
)

UPDATE_CALENDAR_EVENT = ThinkSettingsV1FunctionsItem(
    name="update_calendar_event",
    description=(
        "Update an existing Google Calendar event when the user wants to "
        "change, reschedule, or modify an appointment. Only pass fields that change."
    ),
    parameters={
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "The event ID returned when the event was created",
            },
            "title": {
                "type": "string",
                "description": "New title",
            },
            "start_iso": {
                "type": "string",
                "description": "New start time in ISO format",
            },
            "end_iso": {
                "type": "string",
                "description": "New end time in ISO format",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "New duration in minutes when end_iso is not given",
            },
            "description": {
                "type": "string",
                "description": "New event notes",
            },
        },
        "required": ["event_id"],
    },
)

DELETE_CALENDAR_EVENT = ThinkSettingsV1FunctionsItem(
    name="delete_calendar_event",
    description=(
        "Delete or cancel a Google Calendar event when the user wants to "
        "remove, cancel, or delete an appointment."
    ),
    parameters={
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "The event ID to delete",
            },
        },
        "required": ["event_id"],
    },
)

ALL_FUNCTIONS = [CREATE_CALENDAR_EVENT, UPDATE_CALENDAR_EVENT, DELETE_CALENDAR_EVENT]
