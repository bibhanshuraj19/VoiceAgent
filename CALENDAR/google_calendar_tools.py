from deepgram.types.think_settings_v1functions_item import ThinkSettingsV1FunctionsItem

CALENDAR_FUNCTION = ThinkSettingsV1FunctionsItem(
    name="create_calendar_event",
    description=(
        "Create an appointment on the user's Google Calendar when they ask to "
        "schedule, book, reserve, or add a meeting or appointment. Use a clear title. "
        "start_iso must be ISO 8601 with date and time."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short event title or subject",
            },
            "start_iso": {
                "type": "string",
                "description": "Start date-time in ISO 8601, e.g. 2026-04-05T14:30:00",
            },
            "end_iso": {
                "type": "string",
                "description": "End date-time in ISO 8601 (optional, omit if using duration)",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Length in minutes when end_iso is omitted and set default to 45 minutes",
            },
            "description": {
                "type": "string",
                "description": "Optional notes for the calendar event description",
            },
        },
        "required": ["title", "start_iso"],
    },
)

ALL_FUNCTIONS = [CALENDAR_FUNCTION]
