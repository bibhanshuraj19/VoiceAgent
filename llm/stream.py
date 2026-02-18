import logging
import time
from openai import OpenAI
from config import OPENAI_API_KEY, LLM_MODEL

log = logging.getLogger("llm")

class LLMStream:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def stream(
        self,
        messages: list[dict],
        interrupted_flag,        # threading.Event
    ):
        """
        Streams tokens from OpenAI.
        Yields string tokens.
        Stops early if interrupted_flag is set.
        """
        t0 = time.perf_counter()
        first = True

        try:
            stream = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                stream=True,
            )

            for chunk in stream:
                if interrupted_flag.is_set():
                    log.info("LLM stream interrupted by user.")
                    break

                content = chunk.choices[0].delta.content
                if content:
                    if first:
                        log.info(f"LLM TTFT: {(time.perf_counter() - t0) * 1000:.0f}ms")
                        first = False
                    yield content

        except Exception as e:
            log.error(f"LLM stream error: {e}")