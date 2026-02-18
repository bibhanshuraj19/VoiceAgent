import time
import logging
import uuid
from session.state import VoiceSession

log = logging.getLogger("session")

class SessionManager:
    def __init__(self, session_ttl: int = 1800):
        self.sessions: dict[str, VoiceSession] = {}
        self.session_ttl: int = session_ttl          # typo fixed: self_session_ttl → self.session_ttl
        log.info(f"SessionManager initialized. TTL={session_ttl}s")

    def create(self, system_prompt: str, user_id: str = None) -> VoiceSession:
        """Create and register a new session."""
        session = VoiceSession(                      # works now because @dataclass gives __init__
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            created_at=time.time(),
            last_active=time.time(),
            messages=[{"role": "system", "content": system_prompt}],
            system_prompt=system_prompt,
        )
        self.sessions[session.session_id] = session
        log.info(f"Session created: {session.session_id} user={user_id}")
        return session

    def get(self, session_id: str) -> VoiceSession | None:
        """Fetch session and refresh its last_active timestamp."""
        session = self.sessions.get(session_id)
        if session:
            session.last_active = time.time()        # this was already correct in your code
            log.debug(f"Session accessed: {session_id}")
        else:
            log.warning(f"Session not found: {session_id}")
        return session