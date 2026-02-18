import logging
import miniaudio
from config import SPEAKER_SAMPLE_RATE, AUDIO_CHANNELS

log = logging.getLogger("audio.playback")

class SpeakerPlayback:
    def __init__(self):
        self.device = miniaudio.PlaybackDevice(
            sample_rate=SPEAKER_SAMPLE_RATE,
            nchannels=AUDIO_CHANNELS,
            format=miniaudio.SampleFormat.SIGNED16,
        )
        self.device.start()
        log.info(f"Speaker playback started: {self.device.name}")

    def write(self, audio_bytes: bytes):
        self.device.write(audio_bytes)

    def close(self):
        try:
            self.device.close()
            log.info("Speaker playback closed.")
        except Exception as e:
            log.error(f"Error closing speaker: {e}")