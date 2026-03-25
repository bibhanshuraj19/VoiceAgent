import os
<<<<<<< HEAD
=======
import json
>>>>>>> 3c0c230961c2132e8b7a705837ba4f265b470654
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

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY not set")

<<<<<<< HEAD
=======
    def _load_knowledge(self):
        try:
            with open("knowledge.json", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Could not load knowledge: {e}")
            return {}

    def _build_prompt(self):
        knowledge = json.dumps(self._load_knowledge(), separators=(",", ":"))
        return f"{SYSTEM_PROMPT}\n\nKnowledge Base:\n{knowledge}\n"

>>>>>>> 3c0c230961c2132e8b7a705837ba4f265b470654
    def settings(self):
        return AgentV1Settings(
            audio=AgentV1SettingsAudio(
                input=AgentV1SettingsAudioInput(encoding="linear16", sample_rate=AudioManager.RATE),
                output=AgentV1SettingsAudioOutput(encoding="linear16", sample_rate=AudioManager.RATE, container="none"),
            ),
            agent=AgentV1SettingsAgent(
                language="en",
                listen=get_stt_settings(),
<<<<<<< HEAD
                think=get_llm_settings(SYSTEM_PROMPT),
=======
                think=get_llm_settings(self._build_prompt()),
>>>>>>> 3c0c230961c2132e8b7a705837ba4f265b470654
                speak=get_tts_settings(),
                greeting=GREETING,
            ),
        )