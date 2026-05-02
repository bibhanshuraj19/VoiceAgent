from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from deepgram import DeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v1.types.listen_v1results import ListenV1Results
from deepgram.listen.v1.types.listen_v1speech_started import ListenV1SpeechStarted


class DeepgramSTT:
    """Minimal streaming wrapper around Deepgram's websocket STT."""

    _KEEPALIVE_INTERVAL = 5.0

    def __init__(
        self,
        *,
        api_key: str,
        sample_rate: int = 16000,
        channels: int = 1,
        model: str = "nova-3",
        language: str = "multi",
        endpointing_ms: int = 600,
        interim_results: bool = False,
        on_transcript: Callable[[str], None],
        on_speech_started: Callable[[], None],
    ):
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY is required for DeepgramSTT")

        self._api_key = api_key
        self._sample_rate = sample_rate
        self._channels = channels
        self._model = model
        self._language = language
        self._endpointing_ms = endpointing_ms
        self._interim = interim_results
        self._on_text = on_transcript
        self._on_start = on_speech_started

        self._paused = True
        self._alive = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._keepalive_thread: Optional[threading.Thread] = None
        self._ws = None
        self._ws_lock = threading.Lock()
        self._ready = threading.Event()
        self._connected = threading.Event()
        self._closing = threading.Event()
        self._speech_detected = False
        self._last_error: Optional[str] = None

    def start(self) -> None:
        self._ready.clear()
        self._connected.clear()
        self._closing.clear()
        self._last_error = None
        self._alive.set()
        self._thread = threading.Thread(target=self._run, daemon=True, name="deepgram-stt")
        self._thread.start()
        if not self._ready.wait(timeout=10):
            raise RuntimeError("Deepgram STT connection timed out")
        if not self._connected.is_set():
            raise RuntimeError(self._last_error or "Deepgram STT failed to connect")

    def pause(self) -> None:
        self._paused = True
        self._speech_detected = False

    def resume(self) -> None:
        self._paused = False

    def feed(self, chunk: bytes) -> None:
        if self._paused or not chunk or not self._alive.is_set():
            return
        with self._ws_lock:
            ws = self._ws
        if ws is None:
            return
        try:
            ws.send_media(chunk)
        except Exception:
            pass

    def close(self) -> None:
        self._closing.set()
        self._alive.clear()
        with self._ws_lock:
            ws = self._ws
        if ws is not None:
            try:
                ws.send_close_stream()
            except Exception:
                pass
        if self._keepalive_thread and self._keepalive_thread.is_alive():
            self._keepalive_thread.join(timeout=2)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        with self._ws_lock:
            self._ws = None
        self._connected.clear()

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def _keepalive_loop(self) -> None:
        while self._alive.is_set():
            time.sleep(self._KEEPALIVE_INTERVAL)
            if not self._alive.is_set():
                break
            with self._ws_lock:
                ws = self._ws
            if ws is None:
                continue
            try:
                ws.send_keep_alive()
            except Exception:
                pass

    def _run(self) -> None:
        try:
            client = DeepgramClient(api_key=self._api_key)
            with client.listen.v1.connect(
                model=self._model,
                language=self._language,
                encoding="linear16",
                channels=str(self._channels),
                sample_rate=str(self._sample_rate),
                smart_format="true",
                punctuate="true",
                interim_results="true" if self._interim else "false",
                endpointing=str(self._endpointing_ms),
                vad_events="true",
            ) as ws:
                with self._ws_lock:
                    self._ws = ws

                ws.on(EventType.OPEN, self._on_open)
                ws.on(EventType.MESSAGE, self._on_message)
                ws.on(EventType.ERROR, self._on_error)
                ws.on(EventType.CLOSE, self._on_close)

                self._keepalive_thread = threading.Thread(
                    target=self._keepalive_loop,
                    daemon=True,
                    name="deepgram-keepalive",
                )
                self._keepalive_thread.start()

                ws.start_listening()
        except Exception as exc:
            self._last_error = f"Deepgram STT connection error: {exc}"
            print(f"[DeepgramSTT] connection error: {exc}")
        finally:
            self._connected.clear()
            with self._ws_lock:
                self._ws = None
            self._ready.set()

    def _on_open(self, _open_data) -> None:
        print("[DeepgramSTT] Connected")
        self._connected.set()
        self._ready.set()

    def _on_message(self, message) -> None:
        if isinstance(message, ListenV1SpeechStarted):
            if not self._speech_detected:
                self._speech_detected = True
                try:
                    self._on_start()
                except Exception:
                    pass
            return

        if not isinstance(message, ListenV1Results):
            return

        try:
            text = (message.channel.alternatives[0].transcript or "").strip()
        except (AttributeError, IndexError):
            return
        if not text:
            return

        if not self._speech_detected:
            self._speech_detected = True
            try:
                self._on_start()
            except Exception:
                pass

        if message.is_final and (message.speech_final or not self._interim):
            self._speech_detected = False
            try:
                self._on_text(text)
            except Exception as exc:
                print(f"[DeepgramSTT] on_transcript error: {exc}")

    def _on_error(self, error) -> None:
        self._last_error = str(error)
        print(f"[DeepgramSTT] Error: {error}")

    def _on_close(self, close_data) -> None:
        self._connected.clear()
        if self._alive.is_set() and not self._closing.is_set():
            self._last_error = f"Deepgram STT closed unexpectedly: {close_data}"
        print(f"[DeepgramSTT] Closed: {close_data}")
