from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional


_TOOL_OPEN = re.compile(r"<\s*tool\s*>", re.IGNORECASE)
_TOOL_CLOSE = re.compile(r"<\s*/\s*tool\s*>", re.IGNORECASE)


@dataclass
class ToolCall:
    name: str
    arguments: dict
    raw: str


class ToolStreamParser:
    def __init__(self):
        self._buffer = ""
        self._inside = False

    def feed(self, text: str) -> List[object]:
        out: List[object] = []
        if not text:
            return out
        self._buffer += text
        while True:
            if self._inside:
                m = _TOOL_CLOSE.search(self._buffer)
                if not m:
                    return out
                payload = self._buffer[: m.start()]
                self._buffer = self._buffer[m.end():]
                self._inside = False
                call = self._parse_tool(payload)
                if call is not None:
                    out.append(call)
            else:
                m = _TOOL_OPEN.search(self._buffer)
                if not m:
                    safe = self._safe_prefix_len(self._buffer)
                    if safe > 0:
                        out.append(self._buffer[:safe])
                        self._buffer = self._buffer[safe:]
                    return out
                before = self._buffer[: m.start()]
                if before:
                    out.append(before)
                self._buffer = self._buffer[m.end():]
                self._inside = True

    def flush(self) -> List[object]:
        buf = self._buffer
        self._buffer = ""
        if not buf or self._inside:
            self._inside = False
            return []
        return [buf]

    @staticmethod
    def _safe_prefix_len(buf: str) -> int:
        idx = buf.rfind("<")
        if idx == -1:
            return len(buf)
        tail = buf[idx:].lower()
        if tail.startswith("<") and ("tool" in tail or len(tail) < 7):
            return idx
        return len(buf)

    @staticmethod
    def _parse_tool(payload: str) -> Optional[ToolCall]:
        raw = payload.strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        name = data.get("name") or data.get("tool") or data.get("function")
        args = data.get("args") or data.get("arguments") or data.get("parameters") or {}
        if not isinstance(name, str) or not isinstance(args, dict):
            return None
        return ToolCall(name=name, arguments=args, raw=raw)
