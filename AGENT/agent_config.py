import os

from dotenv import load_dotenv
from deepgram.agent.v1.types import (
    AgentV1Settings,
    AgentV1SettingsAgent,
    AgentV1SettingsAudio,
    AgentV1SettingsAudioInput,
    AgentV1SettingsAudioOutput,
)

from AUDIO.audio_manager import AudioManager
from STT.stt_provider import get_stt_settings
from TTS.tts_provider import get_tts_settings
from LLM.llm_provider import get_llm_settings
from prompts import SYSTEM_PROMPT, GREETING


class AgentConfig:
    """Loads environment config and builds the Deepgram agent settings."""

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY is not set in the environment")

    def settings(self) -> AgentV1Settings:
        return AgentV1Settings(
            type="Settings",
            audio=AgentV1SettingsAudio(
                input=AgentV1SettingsAudioInput(
                    encoding="linear16",
                    sample_rate=AudioManager.RATE,
                ),
                output=AgentV1SettingsAudioOutput(
                    encoding="linear16",
                    sample_rate=AudioManager.RATE,
                    container="none",
                ),
            ),
            agent=AgentV1SettingsAgent(
                language="en",
                listen=get_stt_settings(),
                think=get_llm_settings(SYSTEM_PROMPT),
                speak=get_tts_settings(),
                greeting=GREETING,
            ),
        )
