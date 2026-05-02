from __future__ import annotations

import re
import time
from typing import Any, Dict, Iterable, Iterator, List, Optional

from openai import OpenAI


class LLMStreamError(RuntimeError):
    pass


class LLMFirstTokenTimeout(LLMStreamError):
    pass


_REASONING_BLOCK_RE = re.compile(
    r"<\s*(think|thinking|scratchpad|reasoning|analysis|reflection)\s*[^>]*>.*?"
    r"</\s*\1\s*>",
    re.DOTALL | re.IGNORECASE,
)

_REASONING_OPEN_RE = re.compile(
    r"<\s*(think|thinking|scratchpad|reasoning|analysis|reflection)\s*[^>]*>.*",
    re.DOTALL | re.IGNORECASE,
)

_PREAMBLES = (
    "translation:",
    "translated text:",
    "translated:",
    "here is the translation",
    "here's the translation",
    "answer:",
    "output:",
    "response:",
    "final answer:",
)


def _sanitize(text: str) -> str:
    if not text:
        return text
    cleaned = _REASONING_BLOCK_RE.sub("", text)
    cleaned = _REASONING_OPEN_RE.sub("", cleaned)
    cleaned = cleaned.strip().strip("`")
    low = cleaned.lower()
    for prefix in _PREAMBLES:
        if low.startswith(prefix):
            cleaned = cleaned[len(prefix):].lstrip(" :-\n\"'")
            break
    return cleaned.strip()


class NebiusLLMProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "meta-llama/Llama-3.3-70B-Instruct",
        base_url: str = "https://api.studio.nebius.com/v1/",
        temperature: float = 0.3,
        max_tokens: int = 700,
        first_token_timeout: float = 6.0,
        connect_retry_attempts: int = 1,
        request_timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("NEBIUS_API_KEY is required for NebiusLLMProvider")
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=request_timeout)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._first_token_timeout = max(first_token_timeout, 0.0)
        self._connect_retry_attempts = max(connect_retry_attempts, 0)

    def stream(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        last_exc: Optional[BaseException] = None
        attempts = self._connect_retry_attempts + 1
        for attempt in range(attempts):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    stream=True,
                    temperature=self._temperature if temperature is None else temperature,
                    max_tokens=self._max_tokens if max_tokens is None else max_tokens,
                )
            except Exception as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(0.3 * (attempt + 1))
                    continue
                raise LLMStreamError(f"LLM connect failed: {exc}") from exc

            emitted_any = False
            try:
                for event in self._consume(response, started_at=time.monotonic()):
                    if event.get("type") == "text" and event.get("content"):
                        emitted_any = True
                    yield event
                return
            except LLMFirstTokenTimeout as exc:
                last_exc = exc
                if emitted_any or attempt + 1 >= attempts:
                    raise
                continue
            except Exception as exc:
                if emitted_any:
                    raise LLMStreamError(f"LLM stream error: {exc}") from exc
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(0.3 * (attempt + 1))
                    continue
                raise LLMStreamError(f"LLM stream error: {exc}") from exc

        if last_exc is not None:
            raise LLMStreamError(str(last_exc)) from last_exc

    def _consume(
        self,
        stream: Iterable[Any],
        *,
        started_at: Optional[float] = None,
    ) -> Iterator[Dict[str, Any]]:
        finish_reason: Optional[str] = None
        buffer = ""
        inside_reasoning = False
        emitted_any = False
        deadline = (
            (started_at + self._first_token_timeout)
            if started_at is not None and self._first_token_timeout > 0
            else None
        )
        for chunk in stream:
            if deadline is not None and not emitted_any and time.monotonic() > deadline:
                raise LLMFirstTokenTimeout(
                    f"First token not received within {self._first_token_timeout:.1f}s"
                )
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            content = getattr(delta, "content", None) or ""
            finish_reason = getattr(choice, "finish_reason", None) or finish_reason
            if not content:
                continue

            buffer += content
            while True:
                if inside_reasoning:
                    end = re.search(
                        r"</\s*(think|thinking|scratchpad|reasoning|analysis|reflection)\s*>",
                        buffer,
                        re.IGNORECASE,
                    )
                    if not end:
                        buffer = ""
                        break
                    buffer = buffer[end.end():]
                    inside_reasoning = False
                else:
                    start = re.search(
                        r"<\s*(think|thinking|scratchpad|reasoning|analysis|reflection)\s*[^>]*>",
                        buffer,
                        re.IGNORECASE,
                    )
                    if not start:
                        emit = buffer
                        buffer = ""
                        if emit:
                            emitted_any = True
                            yield {"type": "text", "content": emit}
                        break
                    emit = buffer[:start.start()]
                    buffer = buffer[start.end():]
                    if emit:
                        emitted_any = True
                        yield {"type": "text", "content": emit}
                    inside_reasoning = True

        if buffer and not inside_reasoning:
            yield {"type": "text", "content": buffer}
        yield {"type": "done", "finish_reason": finish_reason or "stop"}

    def complete(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> str:
        attempts = self._connect_retry_attempts + 1
        last_exc: Optional[BaseException] = None
        for attempt in range(attempts):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    stream=False,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                return ""

            try:
                raw = response.choices[0].message.content or ""
            except (AttributeError, IndexError):
                return ""
            return _sanitize(raw)

        if last_exc is not None:
            return ""
        return ""
