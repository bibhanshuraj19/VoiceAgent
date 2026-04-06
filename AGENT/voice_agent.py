import time
import threading

import pyaudio
from deepgram import DeepgramClient
from deepgram.core.events import EventType

from AUDIO.audio_manager import AudioManager
from SESSION.session_manager import SessionManager
from AGENT.agent_config import AgentConfig
from AGENT.event_handler import EventHandler


class VoiceAgent:
    """Top-level orchestrator: wires audio, events, and the Deepgram WS."""

    def __init__(self):
        self.config = AgentConfig()
        self.audio = AudioManager()
        self.session = SessionManager(max_history=50)
        self.events = EventHandler(self.audio, self.session)
        self._alive = threading.Event()

    def run(self):
        self._alive.set()
        self.audio.open_speaker()
        print("Starting connection...")

        with DeepgramClient(api_key=self.config.api_key).agent.v1.connect() as ws:
            print("Connected. Starting agent...\n")

            self.events.bind_ws(ws)
            ws.on(EventType.OPEN, self.events.on_open)
            ws.on(EventType.MESSAGE, self.events.on_message)
            ws.on(EventType.ERROR, self.events.on_error)
            ws.on(EventType.CLOSE, lambda evt: self.events.on_close(self._alive, evt))

            ws.send_settings(self.config.settings())

            listener = threading.Thread(target=ws.start_listening, daemon=True)
            listener.start()

            def on_mic_data(in_data, _frames, _time, _status):
                if self._alive.is_set():
                    ws.send_media(in_data)
                return (None, pyaudio.paContinue)

            self.audio.open_mic(callback=on_mic_data)

            try:
                while self._alive.is_set():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\nStopping...")
            finally:
                self._alive.clear()
                listener.join(timeout=2)
                try:
                    ws.close()
                except Exception:
                    pass
                self.audio.close()
                self.session.save()
                print("Shutdown complete.")
