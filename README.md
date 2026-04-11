# 🎙️ Voice Agent

A locally hosted, real-time conversational voice agent built on the **Deepgram WebSocket API**. It listens via microphone, understands speech, reasons with GPT-4o, speaks back using Deepgram Aura-2 TTS, and can book/update/delete events on Google Calendar — all hands-free.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        VoiceAgent                       │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐  ┌──────────────┐  │
│  │ AudioManager │   │ AgentConfig  │  │SessionMgr    │  │
│  │  (PyAudio)   │   │ (DG settings)│  │(turn history)│  │
│  └──────┬───────┘   └──────┬───────┘  └──────┬───────┘  │
│         │                  │                 │          │
│         └──────────────────▼─────────────────┘          │
│                     EventHandler                        │
│                          │                              │
│         ┌────────────────┼────────────────┐             │
│         ▼                ▼                ▼             │
│    Audio bytes    ConversationText   FunctionCall       │
│    → speaker      → session log      → CALENDAR         │
└─────────────────────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    Deepgram Pipeline    │
              │  STT: nova-3            │
              │  LLM: gpt-4o            │
              │  TTS: aura-2-odysseus   │
              └─────────────────────────┘
```

### Module Map

| Package | Responsibility |
|---|---|
| `AGENT/` | `VoiceAgent` orchestrator, `AgentConfig` (settings builder), `EventHandler` (WS event routing) |
| `AUDIO/` | `AudioManager` — PyAudio mic input, speaker output, interrupt/drain queue |
| `STT/` | Deepgram nova-3 speech-to-text settings |
| `LLM/` | GPT-4o think settings + function list injection |
| `TTS/` | Deepgram aura-2-odysseus-en voice settings |
| `CALENDAR/` | Google Calendar CRUD (create / update / delete), credential refresh, tool definitions |
| `SESSION/` | Per-session turn history with JSON persistence under `Zessions/` |
| `prompts.py` | System prompt, knowledge base JSON, IST timestamp injection |

---

## Features

- **Real-time voice conversation** over Deepgram's agent WebSocket
- **STT** — Deepgram nova-3 (low-latency, high-accuracy)
- **LLM** — OpenAI GPT-4o via Deepgram's think layer
- **TTS** — Deepgram Aura-2 (`aura-2-odysseus-en`)
- **Barge-in / interruption** — user speech mid-response clears the audio queue instantly
- **Google Calendar tool calls** — create, update, and delete events by voice
- **Education counselor persona** — scoped knowledge base (UG/PG degrees, streams, specializations)
- **Multilingual** — responds in English, Hindi (Devanagari), or Hinglish based on user input
- **Session logging** — every conversation saved as a timestamped JSON under `Zessions/`
- **No browser OAuth flow** — credentials loaded entirely from `.env`

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.12.x |
| pyenv + pyenv-virtualenv | any recent |
| PortAudio (for PyAudio) | system-level |
| Deepgram account | API key required |
| OpenAI account | via Deepgram think layer |
| Google Cloud project | OAuth 2.0 desktop credentials |

Install PortAudio (needed by PyAudio):

```bash
# macOS
brew install portaudio

# Ubuntu / Debian
sudo apt-get install portaudio19-dev
```

---

## Installation

```bash
# 1. Install Python via pyenv
brew install pyenv pyenv-virtualenv
pyenv install 3.12.13
pyenv virtualenv 3.12.13 voice-agent

# 2. Clone and enter the project
git clone <your-repo-url>
cd VoiceAgent

# 3. Activate the virtualenv
pyenv local voice-agent

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Copy the example env file and fill in your credentials:

```bash
cp .env.examples .env
```

### Required keys

```env
# Deepgram
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# Google Calendar OAuth (no browser flow — use refresh token directly)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REFRESH_TOKEN=your_google_refresh_token
```

### Optional keys

```env
# Sarvam AI (if switching TTS provider)
SARVAMAI_API_KEY=your_sarvamai_api_key_here

# Timezone for calendar events (default: Asia/Kolkata)
GOOGLE_CALENDAR_TIMEZONE=Asia/Kolkata
```

### Getting your Google OAuth refresh token

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services → Credentials**
2. Create an **OAuth 2.0 Client ID** of type **Desktop App**
3. Enable the **Google Calendar API** for your project
4. Run a one-time browser auth flow to obtain `client_id`, `client_secret`, and `refresh_token`
5. Paste all three into `.env` — the agent refreshes the access token automatically on every call

---

## Running

```bash
python main.py
```

The agent will:
1. Connect to Deepgram's agent WebSocket
2. Send settings (STT + LLM + TTS + tool definitions)
3. Open your microphone and speaker
4. Greet you and start listening

Press **Ctrl+C** to stop. The session is saved automatically on shutdown.

---

## Voice Commands

### Education queries
> "What are the specializations under B.Tech Computer Science?"
> "Tell me about postgraduate options in law."
> "What is the duration of MBBS?"

### Calendar
> "Schedule a counseling session tomorrow at 3 PM."
> "Move my appointment to Friday at 11 AM."
> "Cancel my meeting."

---

## Project Structure

```
VoiceAgent/
├── main.py                          # Entry point + Deepgram WS patch
├── prompts.py                       # System prompt, knowledge base, IST injection
├── requirements.txt
├── .env.examples
│
├── AGENT/
│   ├── voice_agent.py               # Top-level orchestrator
│   ├── agent_config.py              # Deepgram AgentV1Settings builder
│   └── event_handler.py             # WS event routing + function call dispatch
│
├── AUDIO/
│   └── audio_manager.py             # PyAudio mic/speaker, queue, interrupt
│
├── STT/
│   └── stt_provider.py              # nova-3 settings
│
├── LLM/
│   └── llm_provider.py              # GPT-4o + tool injection
│
├── TTS/
│   └── tts_provider.py              # aura-2-odysseus-en settings
│
├── CALENDAR/
│   ├── __init__.py                  # dispatch_function router
│   ├── google_calendar_credentials.py   # OAuth token refresh
│   ├── google_calendar_tools.py     # ThinkSettingsV1FunctionsItem definitions
│   ├── google_create_event.py
│   ├── google_update_event.py
│   └── google_delete_event.py
│
├── SESSION/
│   └── session_manager.py           # Turn history + JSON save
│
└── Zessions/                        # Auto-created — session logs land here
    └── <uuid>.json
```

---

## Session Logs

Every conversation is saved under `Zessions/<session-id>.json`:

```json
{
  "session_id": "a34412e1-...",
  "started_at": "2026-03-11T08:24:35+00:00",
  "ended_at": "2026-03-11T08:24:43+00:00",
  "duration_seconds": 8.3,
  "total_turn_count": 1,
  "turns": [
    { "role": "assistant", "content": "Hi, I am your education counselor...", "timestamp": "..." }
  ]
}
```

---

## Extending

### Swap the TTS provider

Edit `TTS/tts_provider.py`. To use Sarvam AI instead of Deepgram Aura-2, return a `SpeakSettingsV1Provider_Sarvam` object and set `SARVAMAI_API_KEY` in `.env`.

### Add a new calendar tool

1. Define a `ThinkSettingsV1FunctionsItem` in `CALENDAR/google_calendar_tools.py`
2. Add the implementation in a new `CALENDAR/google_<action>_event.py`
3. Register it in `CALENDAR/__init__.py` — both the import and the `_DISPATCH` dict

### Change the LLM

Edit `LLM/llm_provider.py`. The provider block accepts any model string supported by Deepgram's think layer.

### Expand the knowledge base

The education knowledge base lives entirely in `prompts.py` as `KNOWLEDGE_BASE_JSON`. Edit that dict to add new streams, degrees, or specializations — the LLM is instructed to only surface facts present in it.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `DEEPGRAM_API_KEY is not set` | Missing env var | Add key to `.env` |
| `PyAudio` install fails | Missing PortAudio | `brew install portaudio` or `apt-get install portaudio19-dev` |
| Google Calendar call returns 401 | Expired / wrong credentials | Re-generate refresh token |
| No audio output | Wrong output device | Check system default audio device |
| Agent doesn't respond to barge-in | PyAudio buffer lag | Reduce `CHUNK` in `AudioManager` |

---

## License

MIT