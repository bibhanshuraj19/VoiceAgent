import logging
from deepgram import DeepgramClient
from deepgram.extensions.types.sockets import LiveOptions, LiveTranscriptionEvents
from deepgram.core.options import DeepgramClientOptions
from config import DEEPGRAM_API_KEY, DEEPGRAM_STT_MODEL, AUDIO_CHANNELS, MICROPHONE_SAMPLE_RATE

log = logging.getLogger("stt")

class DeepgramSTT:
    def __init__(self, on_transcript: callable):
        config = DeepgramClientOptions(options={"keepalive": "true"})
        client  = DeepgramClient(DEEPGRAM_API_KEY, config)

        self.socket = client.listen.live.v("1")

        options = LiveOptions(
            model=DEEPGRAM_STT_MODEL,
            language="en-US",
            smart_format=True,
            interim_results=True,
            utterance_end_ms="800",
            vad_events=True,
            endpointing="300",
            encoding="linear16",
            channels=AUDIO_CHANNELS,
            sample_rate=MICROPHONE_SAMPLE_RATE,
        )

        self.socket.on(LiveTranscriptionEvents.Transcript, on_transcript)
        self.socket.on(
            LiveTranscriptionEvents.Error,
            lambda _, e: log.error(f"STT error: {e}")
        )

        if not self.socket.start(options):
            raise RuntimeError("Failed to start Deepgram STT socket.")

        log.info("Deepgram STT socket started.")

    def send(self, audio_bytes: bytes):
        self.socket.send(audio_bytes)

    def close(self):
        try:
            self.socket.finish()
            log.info("Deepgram STT socket closed.")
        except Exception as e:
            log.error(f"Error closing STT socket: {e}")