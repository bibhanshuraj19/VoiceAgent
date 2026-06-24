# Voice Agent

Real-time voice assistant: **Deepgram STT** → **Nebius LLM** → **ElevenLabs TTS**, with Google Calendar tools and an optional local web UI.

## Pipeline

```
Mic → Deepgram nova-3 → Nebius Llama 3.3 → ElevenLabs flash → Speaker
                              ↓
                    Calendar create / update / delete
```

## Setup

```bash
brew install portaudio
pyenv install 3.12.13 && pyenv virtualenv 3.12.13 voice-agent
pyenv local voice-agent
pip install -r requirements.txt
cp .env.examples .env   # fill in API keys
python main.py
```

## Required env

| Key | Purpose |
|---|---|
| `DEEPGRAM_API_KEY` | Streaming speech-to-text |
| `NEBIUS_API_KEY` | LLM (OpenAI-compatible) |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` | Text-to-speech |
| `GOOGLE_CLIENT_ID` / `SECRET` / `REFRESH_TOKEN` | Calendar OAuth |

See `.env.examples` for optional tuning (barge-in, UI port, model names).

## Features

- English + Hindi replies (script/heuristic detection)
- Streaming TTS for English; buffered + translation for Hindi
- Barge-in while the agent speaks
- Calendar booking by voice (`<tool>{...}</tool>` protocol)
- Session logs under `Zessions/`
- Browser UI at `http://127.0.0.1:8765/` when `VOICE_UI_ENABLED=true`

## Layout

```
main.py                 Entry point
AGENT/voice_agent.py    Orchestrator (mic, STT, LLM, TTS, tools)
AGENT/agent_config.py   Env config
AGENT/language.py       Language detection + fallbacks
STT/deepgram_stt.py     Deepgram websocket STT
LLM/nebius_llm_provider.py
TTS/elevenlabs_tts_provider.py
CALENDAR/               Google Calendar CRUD
SESSION/session_manager.py
UI/                     SSE web UI
prompts.py              System prompt + greeting
```

## Voice examples

- "What specializations exist under B.Tech Computer Science?"
- "Schedule a counseling session tomorrow at 3 PM."
- "Cancel my meeting."

## License

MIT
