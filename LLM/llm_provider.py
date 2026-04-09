from deepgram.types.think_settings_v1 import ThinkSettingsV1
from deepgram.types.think_settings_v1provider import ThinkSettingsV1Provider_OpenAi
from CALENDAR.google_calendar_tools import ALL_FUNCTIONS


def get_llm_settings(prompt: str) -> ThinkSettingsV1:
    return ThinkSettingsV1(
        provider=ThinkSettingsV1Provider_OpenAi(
            type="open_ai",
            model="gpt-4o",
            temperature=0.2,
        ),
        prompt=prompt,
        functions=ALL_FUNCTIONS,
    )
