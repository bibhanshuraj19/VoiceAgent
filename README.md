# VoiceAgent


## Project Structure 
voice_agent/
│
├── main.py                  # entry point only, boots the app
│
├── agent/
│   ├── __init__.py
│   ├── voice_agent.py       # VoiceAgent class, run loop
│   ├── turn.py              # _turn(), sentence splitting logic
│   └── interruption.py      # interruption detection and recovery
│
├── session/
│   ├── __init__.py
│   ├── manager.py           # SessionManager class
│   ├── state.py             # VoiceSession dataclass
│   ├── window.py            # sliding window logic
│   ├── summarizer.py        # summarization strategy
│   └── entities.py          # entity extraction strategy
│
├── audio/
│   ├── __init__.py
│   ├── capture.py           # mic capture
│   ├── playback.py          # speaker playback
│   └── config.py            # AUDIO_CHANNELS, SAMPLE_RATES, etc.
│
├── llm/
│   ├── __init__.py
│   ├── stream.py            # _stream_llm(), OpenAI streaming
│   └── prompts.py           # all prompt templates in one place
│
├── stt/
│   ├── __init__.py
│   └── deepgram.py          # Deepgram socket setup, _on_transcript
│
├── tts/
│   ├── __init__.py
│   └── deepgram.py          # _speak(), TTS HTTP call
│
├── knowledge/
│   ├── __init__.py
│   ├── loader.py            # load_knowledge()
│   └── knowledge.json       # your knowledge base
│
├── config.py                # all constants and env vars in one place
└── .env