import logging
import signal
import sys
import threading
import time

from audio.capture import MicCapture
from audio.playback import SpeakerPlayback
from stt.deepgram import DeepgramSTT
from tts.deepgram import DeepgramTTS
from llm.stream import LLMStream
from llm.prompts import SYSTEM_PROMPT_TEMPLATE, GREETING
from knowledge.loader import load_knowledge

log = logging.getLogger("agent")

SENTENCE_ENDINGS = [". ", "? ", "! ", "\n"]

class VoiceAgent:
    def __init__(self):
        self.running     = threading.Event()
        self.interrupted = threading.Event()
        self.speaking    = threading.Event()
        self.running.set()

        self._hist_lock = threading.Lock()
        self._turn_lock = threading.Lock()
        self.history: list[dict] = []

        # Build system prompt
        knowledge       = load_knowledge()
        self.sys_prompt = SYSTEM_PROMPT_TEMPLATE.format(knowledge=knowledge)

        # Audio
        self.mic      = MicCapture()
        self.speaker  = SpeakerPlayback()

        # Components
        self.tts = DeepgramTTS(playback_device=self.speaker.device)
        self.llm = LLMStream()
        self.stt = DeepgramSTT(on_transcript=self._on_transcript)

        log.info("VoiceAgent initialized.")

    # ------------------------------------------------------------------ #
    #  STT Callback                                                        #
    # ------------------------------------------------------------------ #
    def _on_transcript(self, _, result, **kwargs):
        transcript = result.channel.alternatives[0].transcript
        if not transcript:
            return

        if self.speaking.is_set():
            log.info("Barge-in detected — interrupting agent.")
            self.interrupted.set()

        if not result.is_final:
            return

        threading.Thread(
            target=self._turn, args=(transcript,), daemon=True
        ).start()

    # ------------------------------------------------------------------ #
    #  Turn                                                                #
    # ------------------------------------------------------------------ #
    def _turn(self, user_text: str):
        acquired = self._turn_lock.acquire(blocking=False)
        if not acquired:
            return

        try:
            self.interrupted.clear()
            log.info(f"USER: {user_text}")

            # Build messages
            with self._hist_lock:
                self.history.append({"role": "user", "content": user_text})
                messages = [
                    {"role": "system", "content": self.sys_prompt}
                ] + list(self.history)

            buf        = ""
            full_reply = []

            self.speaking.set()
            try:
                for token in self.llm.stream(messages, self.interrupted):
                    if self.interrupted.is_set():
                        break

                    full_reply.append(token)
                    buf += token

                    # Sentence-level TTS streaming
                    for sep in SENTENCE_ENDINGS:
                        idx = buf.find(sep)
                        if idx != -1:
                            sentence = buf[: idx + 1].strip()
                            buf      = buf[idx + 1:]
                            if sentence:
                                self.tts.speak(sentence, self.interrupted)
                            break

                # Speak remainder
                if buf.strip() and not self.interrupted.is_set():
                    self.tts.speak(buf.strip(), self.interrupted)

            finally:
                self.speaking.clear()

            # Persist assistant response
            full_text = "".join(full_reply).strip()
            if full_text:
                with self._hist_lock:
                    self.history.append({"role": "assistant", "content": full_text})
                log.info(f"BOT: {full_text}")

        finally:
            self._turn_lock.release()

    # ------------------------------------------------------------------ #
    #  Mic Loop                                                            #
    # ------------------------------------------------------------------ #
    def _capture_mic(self):
        while self.running.is_set():
            try:
                audio = self.mic.read()
                if audio:
                    self.stt.send(audio)
            except Exception as e:
                log.error(f"Mic capture error: {e}")
                break

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    def _cleanup(self):
        log.info("Shutting down...")
        self.running.clear()
        self.stt.close()
        self.mic.close()
        self.speaker.close()
        log.info("Shutdown complete.")

    # ------------------------------------------------------------------ #
    #  Run                                                                 #
    # ------------------------------------------------------------------ #
    def run(self):
        signal.signal(signal.SIGINT, lambda *_: (self._cleanup(), sys.exit(0)))

        log.info(f"BOT: {GREETING}")
        self.tts.speak(GREETING, self.interrupted)

        threading.Thread(target=self._capture_mic, daemon=True).start()
        log.info("Agent ready. Speak now.")

        while self.running.is_set():
            time.sleep(0.5)