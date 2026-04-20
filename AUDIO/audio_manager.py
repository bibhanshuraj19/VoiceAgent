import queue
import threading
import pyaudio

class AudioManager:
    """Manages mic input and speaker output via PyAudio."""
    RATE = 24000
    CHANNELS = 1
    CHUNK = 320
    WIDTH = 2
    
    def __init__(self):
        self._pa = pyaudio.PyAudio()
        self._mic = None
        self._speaker = None
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._player = None
        self._alive = threading.Event()
        self._interrupted = threading.Event()

    def open_mic(self, callback=None):
        if callback:
            self._mic = self._pa.open(
                format=self._pa.get_format_from_width(self.WIDTH),
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                stream_callback=callback,
            )
            return

        self._mic = self._pa.open(
            format=self._pa.get_format_from_width(self.WIDTH),
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

    def open_speaker(self):
        self._speaker = self._pa.open(
            format=self._pa.get_format_from_width(self.WIDTH),
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK,
        )
        self._alive.set()
        self._player = threading.Thread(target=self._drain_queue, daemon=True)
        self._player.start()

    def _drain_queue(self):
        while self._alive.is_set():
            try:
                chunk = self._queue.get(timeout=0.05)
                if self._speaker is not None:
                    self._speaker.write(chunk)
            except queue.Empty:
                pass

    def play(self, chunk: bytes):
        if self._interrupted.is_set():
            self._interrupted.clear()
        self._queue.put(chunk)

    def interrupt(self):
        self._interrupted.set()
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
