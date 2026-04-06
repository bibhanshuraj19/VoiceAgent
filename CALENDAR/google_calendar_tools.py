from deepgram.types.think_settings_v1functions_item import ThinkSettingsV1FunctionsItem

CALENDAR_FUNCTION = ThinkSettingsV1FunctionsItem(
    name="create_calendar_event",
    description=(
        "Create an appointment on the user's Google Calendar when they ask to "
        "schedule, book, reserve, or add a meeting or appointment. Use a clear title. "
        "start_iso must be ISO  with date and time."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the event given the context of the conversation",
            },
            "start_iso": {
                "type": "string",
                "description": "Start time in ISO format (e.g., 2024-03-20T09:00:00) in the user's timezone",
            },
            "end_iso": {
                "type": "string",
                "description": "End time in ISO format (e.g., 2024-03-20T17:00:00) in the user's timezone",
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
