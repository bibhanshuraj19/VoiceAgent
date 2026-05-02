import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional


class SessionManager:
    SESSION_DIR = "Zessions"

    def __init__(self, session_id=None, max_history=50):
        self.session_id = session_id or str(uuid.uuid4())
        self.max_history = max_history
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.ended_at = None
        self.turns = []
        self._count = 0
        self._on_turn: Optional[Callable[[dict], None]] = None
        self._lock = threading.Lock()
        os.makedirs(self.SESSION_DIR, exist_ok=True)

    def get_history(self):
        with self._lock:
            return list(self.turns)

    def set_on_turn(self, callback: Optional[Callable[[dict], None]]):
        self._on_turn = callback

    def add_turn(self, role: str, content: str):
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self.turns.append(turn)
            self._count += 1
            if len(self.turns) > self.max_history:
                self.turns.pop(0)
        if self._on_turn is not None:
            try:
                self._on_turn(dict(turn))
            except Exception:
                pass

    def save(self):
        self.ended_at = datetime.now(timezone.utc).isoformat()
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.ended_at)
        with self._lock:
            turns = list(self.turns)
            total_turn_count = self._count
        path = os.path.join(self.SESSION_DIR, f"{self.session_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": self.session_id,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "duration_seconds": (end - start).total_seconds(),
                "total_turn_count": total_turn_count,
                "turns": turns,
            }, f, indent=2, ensure_ascii=False)
        print(f"\nSaved: {path}")
