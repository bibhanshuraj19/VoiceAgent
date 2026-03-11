import json
from deepgram.agent.v1.socket_client import V1SocketClient, V1SocketClientResponse
from deepgram.core.events import EventType
from deepgram.core.pydantic_utilities import parse_obj_as
from AGENT.voice_agent import VoiceAgent

def _patched_start_listening(self):
    self._emit(EventType.OPEN, None)
    try:
        for raw in self._websocket:
            if isinstance(raw, bytes):
                self._emit(EventType.MESSAGE, raw)
            else:
                try:
                    parsed = parse_obj_as(V1SocketClientResponse, json.loads(raw))
                    self._emit(EventType.MESSAGE, parsed)
                except Exception:
                    continue
    except Exception as exc:
        self._emit(EventType.ERROR, exc)
    finally:
        self._emit(EventType.CLOSE, None)

V1SocketClient.start_listening = _patched_start_listening

if __name__ == "__main__":
    VoiceAgent().run()