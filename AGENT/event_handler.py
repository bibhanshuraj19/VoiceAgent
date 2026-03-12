from AUDIO.audio_manager import AudioManager
from SESSION.session_manager import SessionManager

class EventHandler:

    def __init__(self, audio: AudioManager, session: SessionManager):
        self.audio = audio
        self.session = session

    def on_open(self, _):
        print("Connected")

    def on_message(self, msg):
        if isinstance(msg, bytes):
            self.audio.play(msg)
            return

        kind = getattr(msg, "type", None)

        if kind == "ConversationText":
            data = msg.to_dict() if hasattr(msg, "to_dict") else msg.__dict__
            role, content = data.get("role", ""), data.get("content", "")
            if role and content:
                self.session.add_turn(role="user" if role == "user" else "assistant", content=content)
                print(f"{'You' if role == 'user' else 'Agent'}: {content}")

        elif kind == "UserStartedSpeaking":
            self.audio.interrupt()
            print("\n[Interrupted — Listening...]")

        elif kind == "AgentThinking":
            print("\n[Thinking...]")

        elif kind == "AgentStartedSpeaking":
            self.audio.clear_interrupt()
            print("[Speaking...]")

    def on_error(self, err):
        print(f"\nError: {err}")

    def on_close(self, keep_running, _):
        keep_running.clear()