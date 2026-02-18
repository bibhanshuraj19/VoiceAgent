import os
from dotenv import load_dotenv

load_dotenv()

# Audio
AUDIO_CHANNELS          = 1
MICROPHONE_SAMPLE_RATE  = 16000
SPEAKER_SAMPLE_RATE     = 24000
BUFFER_CHUNK_SIZE_MS    = 30
BUFFER_CHUNK_SIZE_BYTES = int(MICROPHONE_SAMPLE_RATE * AUDIO_CHANNELS * 2 * BUFFER_CHUNK_SIZE_MS / 1000)  # 960

# LLM
LLM_MODEL = "gpt-4o-mini"

# Deepgram
DEEPGRAM_TTS_URL     = "https://api.deepgram.com/v1/speak"
DEEPGRAM_TTS_MODEL   = "aura-2-thalia-en"
DEEPGRAM_TTS_TIMEOUT = 15
DEEPGRAM_STT_MODEL   = "nova-3"

# Keys
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env")
if not DEEPGRAM_API_KEY:
    raise ValueError("DEEPGRAM_API_KEY not found in .env")