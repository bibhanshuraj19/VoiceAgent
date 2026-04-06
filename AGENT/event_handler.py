import threading
from typing import Any

from deepgram.agent.v1.types.agent_v1function_call_request import AgentV1FunctionCallRequest
from deepgram.agent.v1.types.agent_v1send_function_call_response import AgentV1SendFunctionCallResponse

from AUDIO.audio_manager import AudioManager
from CALENDAR.google_calendar import dispatch_function
from SESSION.session_manager import SessionManager


class EventHandler:
    """Handles all incoming WebSocket events from the Deepgram agent."""

    def __init__(self, audio: AudioManager, session: SessionManager):
        self.audio = audio
        self.session = session
        self._ws: Any = None

    def bind_ws(self, ws: Any) -> None:
        self._ws = ws

    def on_open(self, _open_event):
        print("Connected")

    def on_message(self, message):
        if isinstance(message, bytes):
            self.audio.play(message)
            return

        if isinstance(message, AgentV1FunctionCallRequest):
            self._handle_function_call(message)
            return

        if isinstance(message, dict):
            kind = message.get("type")
        else:
            kind = getattr(message, "type", None)

        if kind == "ConversationText":
            self._handle_conversation_text(message)
        elif kind == "History":
            self._handle_history(message)
        elif kind == "UserStartedSpeaking":
            self.audio.interrupt()
            print("\n[Interrupted — Listening...]")
        elif kind == "AgentThinking":
            print("\n[Thinking...]")
        elif kind == "AgentStartedSpeaking":
            self.audio.clear_interrupt()
            print("[Speaking...]")

    def on_error(self, error):
        print(f"\nError: {error}")

    def on_close(self, keep_running, _close_event):
        keep_running.clear()

    def _handle_conversation_text(self, message):
        data = message.to_dict() if hasattr(message, "to_dict") else message.__dict__
        role = data.get("role", "")
        content = data.get("content", "")
        if role and content:
            self.session.add_turn(
                role="user" if role == "user" else "assistant",
                content=content,
            )
            label = "You" if role == "user" else "Agent"
            print(f"{label}: {content}")

    def _handle_history(self, message):
        """Handle 'History' messages the API sends as raw dicts."""
        if isinstance(message, dict):
            role = message.get("role", "")
            content = message.get("content", "")
        else:
            role = getattr(message, "role", "")
            content = getattr(message, "content", "")
        if role and content:
            self.session.add_turn(
                role="user" if role == "user" else "assistant",
                content=content,
            )

    def _handle_function_call(self, request: AgentV1FunctionCallRequest) -> None:
        if not self._ws:
            print("Function call received but WebSocket not bound — skipping.")
            return

        for fn in request.functions:
            if not fn.client_side:
                continue

            thread = threading.Thread(
                target=self._execute_and_respond,
                args=(fn.id, fn.name, fn.arguments),
                daemon=True,
            )
            thread.start()

    def _execute_and_respond(self, call_id: str, name: str, arguments: str) -> None:
        """Execute a function and send the result back over the WebSocket."""
        print(f"\n[Calling tool: {name}]")
        try:
            result = dispatch_function(name, arguments)
            print(f"[Tool result: {result[:200]}]")
        except Exception as exc:
            import json
            result = json.dumps({"ok": False, "error": str(exc)})
            print(f"[Tool error: {exc}]")

        try:
            self._ws.send_function_call_response(
                AgentV1SendFunctionCallResponse(
                    type="FunctionCallResponse",
                    id=call_id,
                    name=name,
                    content=result,
                )
            )
        except Exception as exc:
            print(f"[Failed to send function response: {exc}]")
