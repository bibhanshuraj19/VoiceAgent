import json
from pydantic import ValidationError
from deepgram.agent.v1.socket_client import V1SocketClient, V1SocketClientResponse
from deepgram.core.events import EventType
from deepgram.core.pydantic_utilities import parse_obj_as
from AGENT.voice_agent import VoiceAgent

KNOWN_WS_TYPES = {
    "FunctionCallResponse", "PromptUpdated", "SpeakUpdated",
    "InjectionRefused", "Welcome", "SettingsApplied", "ConversationText",
    "UserStartedSpeaking", "AgentThinking", "FunctionCallRequest",
    "AgentStartedSpeaking", "AgentAudioDone", "Error", "Warning",
}


def _patched_start_listening(self):
    self._emit(EventType.OPEN, None)
    try:
        for raw in self._websocket:
            if isinstance(raw, bytes):
                self._emit(EventType.MESSAGE, raw)
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "")

            if msg_type not in KNOWN_WS_TYPES:
                self._emit(EventType.MESSAGE, data)
                continue

            try:
                parsed = parse_obj_as(V1SocketClientResponse, data)
                self._emit(EventType.MESSAGE, parsed)
            except ValidationError:
                self._emit(EventType.MESSAGE, data)

    except Exception as exc:
        self._emit(EventType.ERROR, exc)
    finally:
        self._emit(EventType.CLOSE, None)


V1SocketClient.start_listening = _patched_start_listening

if __name__ == "__main__":
    VoiceAgent().run()
