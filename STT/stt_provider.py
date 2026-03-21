from deepgram.agent.v1.types import (
    AgentV1SettingsAgentListen,
    AgentV1SettingsAgentListenProvider_V1,
)

def get_stt_settings():
    return AgentV1SettingsAgentListen(
        provider=AgentV1SettingsAgentListenProvider_V1(type="deepgram", model="nova-3"),
    )