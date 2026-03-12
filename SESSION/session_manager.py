import os
import json
import uuid
from datetime import datetime, timezone

class SessionManager:
    SESSION_DIR = "Zessions"

    def __init__(self, session_id=None, max_history=50):
        self.session_id = session_id or str(uuid.uuid4())
        self.max_history = max_history
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.ended_at = None
        self.turns = []
        self._total_turn_count = 0
        os.makedirs(self.SESSION_DIR, exist_ok=True)

    def get_session_id(self):
        return self.session_id

    def add_turn(self, role: str, content: str):
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.turns.append(turn)
        self._total_turn_count += 1
        if len(self.turns) > self.max_history:
            self.turns.pop(0)

    def save(self):
        self.ended_at = datetime.now(timezone.utc).isoformat()
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.ended_at)
        duration_seconds = (end - start).total_seconds()
        session_data = {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": duration_seconds,
            "total_turn_count": self._total_turn_count,
            "turns": self.turns
        }
        filename = os.path.join(self.SESSION_DIR, f"{self.session_id}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        print(f"\nSession saved: {filename}")
        return filename