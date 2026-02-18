# VoiceAgent

A real-time voice agent built with OpenAI (LLM), Deepgram (STT + TTS), and Python.

---

## Architecture Overview

![Architecture Overview](assets/architecture_overview.png)

Incoming user messages pass through the **Session Analyzer**, which decides which memory strategy to activate. All three strategies feed into a **unified prompt builder** before the LLM call is made.

---

## The Context Stack

![Context Stack](assets/context_stack.png)

Every LLM call is built from four ordered layers:

1. **System Prompt** — persona, rules, and knowledge base. Never trimmed.
2. **Rolling Summary** — compressed record of what was discussed in earlier turns.
3. **Recent Turns** — the exact conversation window (last N turns via sliding window).
4. **Current User Input** — the live message being responded to.

---

## Project Structure

```
voice_agent/
│
├── main.py                        # Entry point — boots the app
│
├── config.py                      # All constants and env vars in one place
│
├── .env                           # API keys (never commit this)
│
├── assets/
│   ├── architecture_overview.png  # Architecture diagram
│   └── context_stack.png          # Context stack diagram
│
├── agent/
│   ├── __init__.py
│   ├── voice_agent.py             # VoiceAgent class, main run loop
│   ├── turn.py                    # _turn(), sentence splitting logic
│   └── interruption.py            # Interruption detection and recovery
│
├── session/
│   ├── __init__.py
│   ├── manager.py                 # SessionManager class
│   ├── state.py                   # VoiceSession dataclass
│   ├── window.py                  # Sliding window logic
│   ├── summarizer.py              # Summarization strategy
│   └── entities.py                # Entity extraction strategy
│
├── audio/
│   ├── __init__.py
│   ├── capture.py                 # Mic capture
│   ├── playback.py                # Speaker playback
│   └── config.py                  # AUDIO_CHANNELS, SAMPLE_RATES, etc.
│
├── llm/
│   ├── __init__.py
│   ├── stream.py                  # OpenAI streaming
│   └── prompts.py                 # All prompt templates in one place
│
├── stt/
│   ├── __init__.py
│   └── deepgram.py                # Deepgram socket setup, _on_transcript
│
├── tts/
│   ├── __init__.py
│   └── deepgram.py                # _speak(), TTS HTTP call
│
└── knowledge/
    ├── __init__.py
    ├── loader.py                  # load_knowledge()
    └── knowledge.json             # Your knowledge base
```

---

## File Status

| File | Status | Notes |
|------|--------|-------|
| `config.py` | ✅ Ready | All constants and env vars |
| `main.py` | ✅ Ready | Entry point only |
| `agent/voice_agent.py` | ✅ Ready | Core agent loop |
| `audio/capture.py` | ✅ Ready | Mic capture via miniaudio |
| `audio/playback.py` | ✅ Ready | Speaker playback via miniaudio |
| `llm/stream.py` | ✅ Ready | OpenAI streaming with TTFT logging |
| `llm/prompts.py` | ✅ Ready | System prompt + greeting |
| `stt/deepgram.py` | ✅ Ready | Deepgram Nova-3 live socket |
| `tts/deepgram.py` | ✅ Ready | Deepgram Aura-2 TTS |
| `knowledge/loader.py` | ✅ Ready | JSON knowledge base loader |
| `session/state.py` | ✅ Ready | VoiceSession dataclass |
| `session/manager.py` | 🔄 Partial | `create()` and `get()` done |
| `agent/turn.py` | ⏳ Pending | Needs session layer first |
| `agent/interruption.py` | ⏳ Pending | Needs session layer first |
| `session/window.py` | ⏳ Pending | Sliding window logic |
| `session/summarizer.py` | ⏳ Pending | Long session summarization |
| `session/entities.py` | ⏳ Pending | Entity extraction + memory |

---

## Audio Settings

| Parameter | Value | Reason |
|-----------|-------|--------|
| `AUDIO_CHANNELS` | 1 (Mono) | Standard for voice |
| `MICROPHONE_SAMPLE_RATE` | 16,000 Hz | Matches Deepgram STT input |
| `SPEAKER_SAMPLE_RATE` | 24,000 Hz | Matches Deepgram TTS output |
| `BUFFER_CHUNK_SIZE_MS` | 30ms | Low latency, stable throughput |
| `BUFFER_CHUNK_SIZE_BYTES` | 960 bytes | Derived: `16000 * 1 * 2 * 0.03` |

---

## Architecture Overview

![Architecture Overview](assets/architecture_overview.png)

Incoming user messages pass through the **Session Analyzer**, which decides which memory strategy to activate. All three strategies feed into a **unified prompt builder** before the LLM call is made.

---

## Session Management Strategy

The agent uses a combined three-layer strategy for managing conversation history:

**1. Sliding Window** — always active. Keeps only the last N turns in the active prompt to control token usage.

**2. Summarization** — triggered when history exceeds a threshold. Compresses old turns into a rolling summary instead of dropping them.

**3. Entity Memory** — runs every N turns. Extracts key facts (name, preferences, intent) and persists them across the full session regardless of window size.

### Trigger Thresholds

| Trigger | Condition | Activates |
|---------|-----------|-----------|
| Always | Every turn | Sliding window |
| Always | Entities exist | Entity injection into prompt |
| Every 2 turns | `turn_count % 2 == 0` | Entity extraction |
| History overflow | Turns since last summary >= 10 | Summarization |
| Token overflow | Total tokens >= 2000 | Summarization |
| Idle timeout | Silence >= 5 minutes | Summarization |

---

## The Context Stack

![Context Stack](assets/context_stack.png)

Every LLM call is built from four ordered layers:

1. **System Prompt** — persona, rules, and knowledge base. Never trimmed.
2. **Rolling Summary** — compressed record of what was discussed in earlier turns.
3. **Recent Turns** — the exact conversation window (last N turns via sliding window).
4. **Current User Input** — the live message being responded to.

---

## Setup

### 1. Install Dependencies

```bash
pip install openai deepgram-sdk miniaudio requests python-dotenv
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_key_here
DEEPGRAM_API_KEY=your_deepgram_key_here
```

### 3. Add Knowledge Base

Create `knowledge/knowledge.json` with your domain knowledge:

```json
{
  "company": "Acme Corp",
  "product": "Voice Assistant v1",
  "faq": {
    "hours": "We are open 9am to 5pm EST.",
    "refund": "Refunds are processed within 5-7 business days."
  }
}
```

### 4. Run

```bash
python main.py
```

---

## How It Works

```
User speaks
    ↓
Mic captures audio (16kHz PCM, 30ms chunks)
    ↓
Deepgram STT (Nova-3) → transcript
    ↓
Interruption check → if agent speaking, stop playback
    ↓
Session history + system prompt → OpenAI (gpt-4o-mini) streaming
    ↓
Sentence-by-sentence → Deepgram TTS (Aura-2)
    ↓
Audio plays on speaker (24kHz PCM)
```

---

## Implementation Phases

| Phase | What | Status |
|-------|------|--------|
| Phase 1 | Complete SessionManager (`end`, `cleanup_expired`) | ⏳ Next |
| Phase 2 | History management (`window.py`, `add_turn`) | ⏳ |
| Phase 3 | Connect session to VoiceAgent | ⏳ |
| Phase 4 | Interruption recovery (`interruption.py`) | ⏳ |
| Phase 5 | Summarization (`summarizer.py`) | ⏳ |
| Phase 6 | Entity memory (`entities.py`) | ⏳ |
| Phase 7 | Persistence (Redis / JSON store) | ⏳ |

---

## Models Used

| Component | Model |
|-----------|-------|
| LLM | `gpt-4o-mini` |
| STT | Deepgram `nova-3` |
| TTS | Deepgram `aura-2-thalia-en` |