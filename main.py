import os

import certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from AGENT.voice_agent import VoiceAgent


if __name__ == "__main__":
    VoiceAgent().run()
