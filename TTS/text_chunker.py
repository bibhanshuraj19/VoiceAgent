from __future__ import annotations

import re
from typing import List


_SENTENCE_TERMINATORS = ".!?।॥"
_SOFT_BREAK_CHARS = ",;:—–-"
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.\!\?।॥])\s+")


class TextChunker:
    def __init__(
        self,
        *,
        min_chunk_chars: int = 6,
        soft_limit_chars: int = 72,
        hard_limit_chars: int = 130,
    ):
        self._min = min_chunk_chars
        self._soft = soft_limit_chars
        self._hard = hard_limit_chars
        self._buf: str = ""

    def feed(self, text: str) -> List[str]:
        if not text:
            return []
        self._buf += text
        return self._drain(force=False)

    def flush(self) -> List[str]:
        leftover = self._buf.strip()
        self._buf = ""
        return [leftover] if leftover else []

    def _drain(self, *, force: bool) -> List[str]:
        out: List[str] = []
        while True:
            chunk = self._next_chunk(force=force)
            if chunk is None:
                break
            out.append(chunk)
        return out

    def _next_chunk(self, *, force: bool) -> str | None:
        buf = self._buf
        if not buf:
            return None

        split_at = self._last_sentence_break(buf)
        if split_at is not None and split_at >= self._min:
            chunk = buf[:split_at].strip()
            self._buf = buf[split_at:].lstrip()
            if chunk:
                return chunk

        if len(buf) >= self._soft:
            split_at = self._last_soft_break(buf, upper=len(buf))
            if split_at is not None and split_at >= self._min:
                chunk = buf[:split_at].strip()
                self._buf = buf[split_at:].lstrip()
                if chunk:
                    return chunk

        if len(buf) >= self._hard:
            split_at = buf.rfind(" ", 0, self._hard)
            if split_at > self._min:
                chunk = buf[:split_at].strip()
                self._buf = buf[split_at:].lstrip()
                if chunk:
                    return chunk

        if force:
            chunk = buf.strip()
            self._buf = ""
            return chunk or None
        return None

    @staticmethod
    def _last_sentence_break(buf: str) -> int | None:
        best: int | None = None
        for match in _SENTENCE_SPLIT_RE.finditer(buf):
            best = match.end()
        if best is None and buf and buf[-1] in _SENTENCE_TERMINATORS:
            best = len(buf)
        return best

    @staticmethod
    def _last_soft_break(buf: str, upper: int) -> int | None:
        best = -1
        for ch in _SOFT_BREAK_CHARS:
            idx = buf.rfind(ch, 0, upper)
            if idx > best:
                best = idx
        if best < 0:
            return None
        end = best + 1
        while end < len(buf) and buf[end].isspace():
            end += 1
        return end
