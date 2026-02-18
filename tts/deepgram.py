import logging
import requests
from config import (
    DEEPGRAM_API_KEY,
    DEEPGRAM_TTS_URL,
    DEEPGRAM_TTS_MODEL,
    DEEPGRAM_TTS_TIMEOUT,
    SPEAKER_SAMPLE_RATE,
)

log = logging.getLogger("tts")

class DeepgramTTS:
    def __init__(self, playback_device):
        self.playback_device = playback_device

    def speak(self, text: str, interrupted_flag) -> bool:
        """
        Calls Deepgram TTS and streams audio to playback device.
        Returns True if completed, False if interrupted.
        """
        if not text or interrupted_flag.is_set():
            return False

        try:
            resp = requests.post(
                DEEPGRAM_TTS_URL,
                params={
                    "model": DEEPGRAM_TTS_MODEL,
                    "encoding": "linear16",
                    "sample_rate": str(SPEAKER_SAMPLE_RATE),
                    "container": "none",
                },
                headers={
                    "Authorization": f"Token {DEEPGRAM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
                timeout=DEEPGRAM_TTS_TIMEOUT,
                stream=True,
            )
            resp.raise_for_status()

            for chunk in resp.iter_content(chunk_size=2048):
                if interrupted_flag.is_set():
                    log.info("TTS playback interrupted.")
                    return False
                if chunk:
                    self.playback_device.write(chunk)

            return True

        except requests.Timeout:
            log.error("TTS request timed out.")
        except Exception as e:
            log.error(f"TTS error: {e}")

        return False