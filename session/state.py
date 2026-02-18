import time
import uuid
import asyncio
from dataclasses import dataclass, field

@dataclass
class VoiceSession:
    # Identity
    session_id: str               = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None           = None

    # Timestamps
    created_at: float             = field(default_factory=time.time)
    last_active: float            = field(default_factory=time.time)

    # Conversation
    messages: list[dict]          = field(default_factory=list)   # full history sent to LLM
    system_prompt: str            = ""
    turn_count: int               = 0

    # Audio state
    audio_buffer: bytes           = b""
    is_playing: bool              = False
    is_speaking: bool             = False

    # Agent state
    interrupted: bool             = False
    responding: bool              = False