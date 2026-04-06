from deepgram.types.speak_settings_v1 import SpeakSettingsV1
from deepgram.types.speak_settings_v1provider import SpeakSettingsV1Provider_Deepgram


def get_tts_settings():
    return SpeakSettingsV1(
        provider=SpeakSettingsV1Provider_Deepgram(type="deepgram", model="aura-2-odysseus-en"),
    )
