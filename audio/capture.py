import logging
import miniaudio
from config import MICROPHONE_SAMPLE_RATE, AUDIO_CHANNELS, BUFFER_CHUNK_SIZE_MS

log = logging.getLogger("audio.capture")

class MicCapture:
    def __init__(self):
        self.device = miniaudio.CaptureDevice(
            sample_rate=MICROPHONE_SAMPLE_RATE,
            nchannels=AUDIO_CHANNELS,
            format=miniaudio.SampleFormat.SIGNED16,
            buffersize_msec=BUFFER_CHUNK_SIZE_MS,
        )
        self.device.start()
        log.info(f"Mic capture started: {self.device.name}")

    def read(self) -> bytes:
        frames = self.device.read(
            num_frames=BUFFER_CHUNK_SIZE_MS * MICROPHONE_SAMPLE_RATE // 1000
        )
        return bytes(frames) if frames else b""

    def close(self):
        try:
            self.device.close()
            log.info("Mic capture closed.")
        except Exception as e:
            log.error(f"Error closing mic: {e}")