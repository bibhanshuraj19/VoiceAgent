import queue
import threading

import pyaudio


class AudioManager:
    """Simple 16 kHz mono mic + speaker manager for the voice agent."""

    RATE = 16000
    CHANNELS = 1
    CHUNK = 320
    WIDTH = 2
    _QUEUE_MAX = 48

    def __init__(self):
        self._pa = pyaudio.PyAudio()
        self._mic = None
        self._speaker = None
        self._frame_bytes = self.CHUNK * self.WIDTH
        self._pending = b""
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=self._QUEUE_MAX)
        self._player = None
        self._alive = threading.Event()
        self._interrupted = threading.Event()
        self._writing = threading.Event()

    def open_mic(self, callback=None):
        options = dict(
            format=self._pa.get_format_from_width(self.WIDTH),
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )
        self._mic = self._pa.open(stream_callback=callback, **options) if callback else self._pa.open(**options)

    def open_speaker(self):
        self._speaker = self._pa.open(
            format=self._pa.get_format_from_width(self.WIDTH),
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK,
        )
        self._alive.set()
        self._player = threading.Thread(target=self._drain_queue, daemon=True, name="audio-player")
        self._player.start()

    def _drain_queue(self):
        while self._alive.is_set():
            try:
                chunk = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if self._interrupted.is_set() or self._speaker is None:
                continue
            self._writing.set()
            try:
                self._speaker.write(chunk)
            finally:
                self._writing.clear()

    def play(self, chunk: bytes):
        if self._interrupted.is_set() or not chunk:
            return
        self._pending += chunk
        while len(self._pending) >= self._frame_bytes:
            part = self._pending[: self._frame_bytes]
            self._pending = self._pending[self._frame_bytes :]
            try:
                self._queue.put(part, timeout=0.15)
            except queue.Full:
                self._pending = part + self._pending
                return

    def is_playing(self) -> bool:
        return self._writing.is_set() or len(self._pending) > 0 or not self._queue.empty()

    def flush_playback_tail(self):
        if self._interrupted.is_set():
            self._pending = b""
            return
        if not self._pending:
            return
        pad = self._frame_bytes - len(self._pending)
        tail = self._pending + (b"\x00" * pad if pad < self._frame_bytes else b"")
        try:
            self._queue.put(tail[: self._frame_bytes], timeout=0.2)
        except queue.Full:
            pass
        self._pending = b""

    def interrupt(self):
        self._interrupted.set()
        self._pending = b""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def clear_interrupt(self):
        self._interrupted.clear()

    def close(self):
        self._alive.clear()
        if self._player:
            self._player.join(timeout=2)
        for stream in (self._mic, self._speaker):
            if stream:
                stream.stop_stream()
                stream.close()
        self._pa.terminate()
