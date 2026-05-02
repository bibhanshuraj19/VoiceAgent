from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import httpx


_LANGUAGE_MAP = {
    "en-IN": "en",
    "en-US": "en",
    "en-GB": "en",
    "en-AU": "en",
    "hi-IN": "hi",
    "bn-IN": "bn",
    "ta-IN": "ta",
    "te-IN": "te",
    "ml-IN": "ml",
    "kn-IN": "kn",
    "gu-IN": "gu",
    "pa-IN": "pa",
}


class ElevenLabsTTSProvider:
    _BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"

    def __init__(
        self,
        *,
        api_key: str | None,
        voice_id: str | None,
        model: str = "eleven_flash_v2_5",
        output_format: str = "pcm_16000",
        optimize_streaming_latency: int = 3,
        connect_retry_attempts: int = 1,
    ):
        self._api_key = (api_key or "").strip()
        self._voice_id = (voice_id or "").strip()
        self._model = model
        self._output_format = output_format
        self._latency = int(optimize_streaming_latency)
        self._connect_retry_attempts = max(connect_retry_attempts, 0)
        self._http = httpx.Client(timeout=httpx.Timeout(10.0, read=30.0))

    @property
    def available(self) -> bool:
        return bool(self._api_key and self._voice_id)

    @property
    def provider_key(self) -> str:
        return f"{self._model}:{self._voice_id or 'missing-voice'}"

    def synthesize(
        self,
        *,
        text: str,
        language_code: str,
        on_chunk: Callable[[bytes], None],
        cancel_event: Optional[threading.Event] = None,
    ) -> bool:
        clean = (text or "").strip()
        if not clean:
            return True
        if not self.available:
            return False

        url = f"{self._BASE_URL}/{self._voice_id}/stream"
        params = {
            "output_format": self._output_format,
            "optimize_streaming_latency": str(self._latency),
        }
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        body = {
            "text": clean,
            "model_id": self._model,
            "language_code": _LANGUAGE_MAP.get(language_code, "hi"),
        }

        attempts = self._connect_retry_attempts + 1
        for attempt in range(attempts):
            if cancel_event is not None and cancel_event.is_set():
                return False
            try:
                return self._stream_request(
                    url=url,
                    params=params,
                    headers=headers,
                    body=body,
                    on_chunk=on_chunk,
                    cancel_event=cancel_event,
                )
            except Exception as exc:
                print(f"[ElevenLabsTTS error {attempt + 1}/{attempts}] {exc}")
                if attempt + 1 >= attempts:
                    return False
                time.sleep(0.15 * (attempt + 1))
        return False

    def _stream_request(
        self,
        *,
        url: str,
        params: dict,
        headers: dict,
        body: dict,
        on_chunk: Callable[[bytes], None],
        cancel_event: Optional[threading.Event],
    ) -> bool:
        residual = b""
        with self._http.stream("POST", url, params=params, headers=headers, json=body) as resp:
            if resp.status_code != 200:
                resp.read()
                print(f"[ElevenLabsTTS] HTTP {resp.status_code}: {resp.text[:200]}")
                return False

            for data in resp.iter_bytes(chunk_size=4096):
                if cancel_event is not None and cancel_event.is_set():
                    return False
                if not data:
                    continue
                combined = residual + data
                aligned = len(combined) - (len(combined) % 2)
                if aligned:
                    on_chunk(combined[:aligned])
                residual = combined[aligned:]
        return True

    def close(self) -> None:
        self._http.close()
