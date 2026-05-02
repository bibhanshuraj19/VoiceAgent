import os

from dotenv import load_dotenv


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


class AgentConfig:
    def __init__(self):
        load_dotenv()

        self.deepgram_api_key = _required("DEEPGRAM_API_KEY")
        self.nebius_api_key = _required("NEBIUS_API_KEY")
        self.elevenlabs_api_key = _required("ELEVENLABS_API_KEY")
        self.elevenlabs_voice_id = _required("ELEVENLABS_VOICE_ID")

        self.deepgram_stt_model = os.getenv("DEEPGRAM_STT_MODEL", "nova-3")
        self.deepgram_stt_language = os.getenv("DEEPGRAM_STT_LANGUAGE", "multi")
        self.deepgram_endpointing_ms = int(os.getenv("DEEPGRAM_ENDPOINTING_MS", "600"))

        self.nebius_base_url = os.getenv(
            "NEBIUS_BASE_URL",
            "https://api.studio.nebius.com/v1/",
        )
        self.nebius_llm_model = os.getenv("NEBIUS_LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
        self.nebius_llm_temperature = float(os.getenv("NEBIUS_LLM_TEMPERATURE", "0.3"))
        self.nebius_llm_max_tokens = int(os.getenv("NEBIUS_LLM_MAX_TOKENS", "320"))
        self.nebius_request_timeout = float(os.getenv("NEBIUS_REQUEST_TIMEOUT", "30.0"))

        self.elevenlabs_tts_model = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")
        self.elevenlabs_output_format = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "pcm_16000")
        self.elevenlabs_latency_mode = int(os.getenv("ELEVENLABS_LATENCY_MODE", "3"))

        self.llm_first_token_timeout = float(os.getenv("LLM_FIRST_TOKEN_TIMEOUT", "6.0"))
        self.llm_connect_retry_attempts = int(os.getenv("LLM_CONNECT_RETRY_ATTEMPTS", "1"))
        self.tts_connect_retry_attempts = int(os.getenv("TTS_CONNECT_RETRY_ATTEMPTS", "1"))
        self.tool_timeout_seconds = float(os.getenv("TOOL_TIMEOUT_SECONDS", "8.0"))
        self.no_transcript_nudge_seconds = float(os.getenv("NO_TRANSCRIPT_NUDGE_SECONDS", "4.0"))
        self.barge_in_enabled = _truthy(os.getenv("BARGE_IN_ENABLED", "true"))
        self.barge_in_rms_threshold = int(os.getenv("BARGE_IN_RMS_THRESHOLD", "950"))
        self.barge_in_frames_required = int(os.getenv("BARGE_IN_FRAMES_REQUIRED", "3"))

        self.voice_ui_enabled = _truthy(os.getenv("VOICE_UI_ENABLED", "true"))
        self.voice_ui_host = os.getenv("VOICE_UI_HOST", "127.0.0.1").strip() or "127.0.0.1"
        self.voice_ui_port = int(os.getenv("VOICE_UI_PORT", "8765"))


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value
