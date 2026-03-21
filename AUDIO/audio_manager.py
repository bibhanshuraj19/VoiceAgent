import queue
import threading
import pyaudio

class AudioManager:
    RATE = 24000
    CHANNELS = 1
    CHUNK = 320
    WIDTH = 2

    def __init__(self):
        self._pa = pyaudio.PyAudio()
        self._mic = None
        self._speaker = None
        self._queue = queue.Queue()
        self._player = None
        self._alive = threading.Event()

    def open_mic(self, callback=None):
        opts = dict(
            format=self._pa.get_format_from_width(self.WIDTH),
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )
        if callback:
            opts["stream_callback"] = callback
        self._mic = self._pa.open(**opts)

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
                self._speaker.write(self._queue.get(timeout=0.05))
            except queue.Empty:
                pass

    def play(self, chunk):
        self._queue.put(chunk)

    def interrupt(self):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def close(self):
        self._alive.clear()
        if self._player:
            self._player.join(timeout=2)
        for stream in (self._mic, self._speaker):
            if stream:
                stream.stop_stream()
                stream.close()
        self._pa.terminate()