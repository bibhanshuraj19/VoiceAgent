from __future__ import annotations

import json
import queue
import threading
from collections import deque
from typing import Deque, Dict, List, Tuple


class UIEventBus:
    """Thread-safe pub/sub bus for local browser UI updates."""

    def __init__(self, *, max_transcripts: int = 24, queue_size: int = 64):
        self._lock = threading.Lock()
        self._next_subscriber = 0
        self._queue_size = max(queue_size, 8)
        self._subscribers: Dict[int, "queue.Queue[str]"] = {}
        self._transcripts: Deque[dict] = deque(maxlen=max_transcripts)
        self._state = "connecting"

    def publish_state(self, state: str) -> None:
        self._publish({"type": "state", "value": state or "connecting"})

    def publish_transcript(self, role: str, text: str) -> None:
        clean = (text or "").strip()
        if not clean:
            return
        role = "user" if role == "user" else "agent"
        self._publish({"type": "transcript", "role": role, "text": clean})

    def subscribe(self) -> Tuple[int, "queue.Queue[str]", List[str]]:
        with self._lock:
            subscriber_id = self._next_subscriber
            self._next_subscriber += 1
            q: "queue.Queue[str]" = queue.Queue(maxsize=self._queue_size)
            self._subscribers[subscriber_id] = q
            snapshot = [json.dumps({"type": "state", "value": self._state})]
            snapshot.extend(json.dumps(event, ensure_ascii=False) for event in self._transcripts)
        return subscriber_id, q, snapshot

    def unsubscribe(self, subscriber_id: int) -> None:
        with self._lock:
            self._subscribers.pop(subscriber_id, None)

    def _publish(self, event: dict) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        stale: List[int] = []
        with self._lock:
            if event.get("type") == "state":
                self._state = str(event.get("value") or "connecting")
            elif event.get("type") == "transcript":
                self._transcripts.append(dict(event))

            for subscriber_id, q in self._subscribers.items():
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        stale.append(subscriber_id)
                        continue
                    try:
                        q.put_nowait(payload)
                    except queue.Full:
                        stale.append(subscriber_id)

            for subscriber_id in stale:
                self._subscribers.pop(subscriber_id, None)
