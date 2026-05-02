from __future__ import annotations

import audioop
import concurrent.futures
import json
import threading
import time
from typing import List, Optional

import pyaudio

from AGENT.agent_config import AgentConfig
from AUDIO.audio_manager import AudioManager
from CALENDAR import dispatch_function
from LLM.confirmations import confirm
from LLM.nebius_llm_provider import NebiusLLMProvider
from LLM.tool_protocol import ToolCall, ToolStreamParser
from SESSION.session_manager import SessionManager
from STT.deepgram_stt import DeepgramSTT
from TTS.elevenlabs_tts_provider import ElevenLabsTTSProvider
from TTS.text_chunker import TextChunker
from UI.event_bus import UIEventBus
from UI.web_ui import VoiceUIWebServer
from prompts import GREETING, build_system_prompt


DEFAULT_LANGUAGE_CODE = "en-IN"
HINDI_LANGUAGE_CODE = "hi-IN"

_LANGUAGE_NAMES = {
    DEFAULT_LANGUAGE_CODE: "english",
    HINDI_LANGUAGE_CODE: "hindi",
}

_HINDI_HINTS = {
    "aap",
    "apka",
    "apki",
    "apko",
    "acha",
    "achha",
    "aaj",
    "batao",
    "bataye",
    "batana",
    "baje",
    "bolo",
    "chahiye",
    "de",
    "dena",
    "dijiye",
    "hai",
    "hain",
    "hoon",
    "hum",
    "hume",
    "ham",
    "hoga",
    "kal",
    "ka",
    "ki",
    "ke",
    "kaise",
    "karo",
    "karna",
    "karni",
    "karne",
    "kijiye",
    "kya",
    "kab",
    "kyu",
    "kyon",
    "liye",
    "main",
    "mera",
    "meri",
    "mere",
    "mujhe",
    "namaste",
    "nahi",
    "par",
    "pe",
    "sirf",
    "samajh",
    "theek",
    "thik",
    "tum",
    "ye",
    "yeh",
}

_ENGLISH_HINTS = {
    "about",
    "appointment",
    "book",
    "course",
    "degree",
    "engineering",
    "hello",
    "help",
    "meeting",
    "move",
    "please",
    "schedule",
    "tell",
    "thanks",
    "today",
    "tomorrow",
    "what",
    "when",
    "where",
}

_DID_NOT_CATCH = {
    DEFAULT_LANGUAGE_CODE: "Sorry, I didn't catch that. Could you say it again?",
    HINDI_LANGUAGE_CODE: "माफ़ कीजिए, मैं समझ नहीं पाया। क्या आप दोबारा बोल सकते हैं?",
}

_LLM_FAILURE = {
    DEFAULT_LANGUAGE_CODE: "I'm having trouble answering right now. Please try again in a moment.",
    HINDI_LANGUAGE_CODE: "मुझे अभी जवाब देने में दिक्कत हो रही है। कृपया थोड़ी देर बाद फिर कोशिश कीजिए।",
}

_CALENDAR_HINTS = {
    "appointment",
    "book",
    "booking",
    "calendar",
    "cancel",
    "delete",
    "meeting",
    "move",
    "reschedule",
    "schedule",
    "slot",
    "अपॉइंटमेंट",
    "कैलेंडर",
    "बुक",
    "बदल",
    "बदलो",
    "मुलाकात",
    "रद्द",
    "शेड्यूल",
}


class VoiceHandler:
    """Minimal voice runtime: Deepgram STT + Nebius LLM + ElevenLabs TTS + calendar + UI."""

    def __init__(self):
        self.cfg = AgentConfig()
        self.audio = AudioManager()
        self.session = SessionManager(max_history=30)
        self.session.set_on_turn(self._on_session_turn)

        self.ui_bus = UIEventBus() if self.cfg.voice_ui_enabled else None
        self.ui_server = (
            VoiceUIWebServer(
                self.ui_bus,
                host=self.cfg.voice_ui_host,
                preferred_port=self.cfg.voice_ui_port,
            )
            if self.ui_bus is not None
            else None
        )

        self.llm = NebiusLLMProvider(
            api_key=self.cfg.nebius_api_key,
            model=self.cfg.nebius_llm_model,
            base_url=self.cfg.nebius_base_url,
            temperature=self.cfg.nebius_llm_temperature,
            max_tokens=self.cfg.nebius_llm_max_tokens,
            first_token_timeout=self.cfg.llm_first_token_timeout,
            connect_retry_attempts=self.cfg.llm_connect_retry_attempts,
            request_timeout=self.cfg.nebius_request_timeout,
        )
        self.tts = ElevenLabsTTSProvider(
            api_key=self.cfg.elevenlabs_api_key,
            voice_id=self.cfg.elevenlabs_voice_id,
            model=self.cfg.elevenlabs_tts_model,
            output_format=self.cfg.elevenlabs_output_format,
            optimize_streaming_latency=self.cfg.elevenlabs_latency_mode,
            connect_retry_attempts=self.cfg.tts_connect_retry_attempts,
        )

        self.pool = concurrent.futures.ThreadPoolExecutor(2, thread_name_prefix="tool")
        self._alive = threading.Event()
        self._busy = threading.Event()
        self._state_lock = threading.Lock()
        self._state = "booting"
        self._last_language_code = DEFAULT_LANGUAGE_CODE
        self._stt: Optional[DeepgramSTT] = None
        self._reply_lock = threading.Lock()
        self._cancel: Optional[threading.Event] = None
        self._timer_lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._barge_in = threading.Event()
        self._barge_in_frames = 0
        self._interrupt_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending_user_text: Optional[str] = None
        self._calendar_lock = threading.Lock()
        self._last_calendar_event: Optional[dict] = None

    def run(self):
        self._alive.set()
        if self.ui_server is not None:
            try:
                self.ui_server.start()
                print(f"Voice UI: {self.ui_server.url}")
            except Exception as exc:
                print(f"[Voice UI] {exc}")

        self._set_state("connecting")
        self.audio.open_speaker()

        def on_transcript(text: str) -> None:
            self._clear_timer()
            clean = (text or "").strip()
            if not clean:
                return
            if self._busy.is_set():
                if self._barge_in.is_set():
                    self._set_pending_user_text(clean)
                return
            print(f"You: {clean}")
            self._start_reply(clean)

        def on_speech_started() -> None:
            self._arm_timer()

        self._stt = DeepgramSTT(
            api_key=self.cfg.deepgram_api_key,
            sample_rate=self.audio.RATE,
            channels=self.audio.CHANNELS,
            model=self.cfg.deepgram_stt_model,
            language=self.cfg.deepgram_stt_language,
            endpointing_ms=self.cfg.deepgram_endpointing_ms,
            on_transcript=on_transcript,
            on_speech_started=on_speech_started,
        )

        print("Connecting to Deepgram STT...")
        try:
            self._stt.start()
        except Exception:
            self.audio.close()
            if self.ui_server is not None:
                self.ui_server.stop()
            raise
        self._stt.resume()
        self._set_state("listening")
        print("Ready.\n")
        self._speak_async(GREETING, DEFAULT_LANGUAGE_CODE, save_turn=True)

        def on_mic_data(in_data, *_):
            if not self._alive.is_set():
                return (None, pyaudio.paContinue)
            if self._busy.is_set():
                if self._handle_barge_in_frame(in_data) and self._stt is not None:
                    self._stt.feed(in_data)
                return (None, pyaudio.paContinue)
            if self._stt is not None:
                self._stt.feed(in_data)
            return (None, pyaudio.paContinue)

        self.audio.open_mic(on_mic_data)

        try:
            while self._alive.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\nStop.")
        finally:
            self._alive.clear()
            self._clear_timer()
            if self._stt is not None:
                self._stt.close()
            self.audio.close()
            self.pool.shutdown(wait=False, cancel_futures=True)
            self.tts.close()
            if self.ui_server is not None:
                self.ui_server.stop()
            self.session.save()

    def _set_state(self, state: str) -> None:
        with self._state_lock:
            self._state = state
        if self.ui_bus is not None:
            self.ui_bus.publish_state(self._ui_state(state))

    @staticmethod
    def _ui_state(state: str) -> str:
        return {
            "booting": "connecting",
            "connecting": "connecting",
            "thinking": "thinking",
            "speaking": "speaking",
            "listening": "listening",
        }.get(state, "connecting")

    def _on_session_turn(self, turn: dict) -> None:
        if self.ui_bus is None:
            return
        role = (turn.get("role") or "").strip().lower()
        text = (turn.get("content") or "").strip()
        if role not in ("user", "assistant") or not text:
            return
        self.ui_bus.publish_transcript("user" if role == "user" else "agent", text)

    def _arm_timer(self) -> None:
        seconds = max(float(self.cfg.no_transcript_nudge_seconds), 0.0)
        if seconds <= 0:
            return
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(seconds, self._on_no_transcript)
            self._timer.daemon = True
            self._timer.start()

    def _clear_timer(self) -> None:
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def _on_no_transcript(self) -> None:
        if not self._alive.is_set() or self._busy.is_set():
            return
        print("[No transcript]")
        self._speak_async(
            _pick_message(_DID_NOT_CATCH, self._last_language_code),
            self._last_language_code,
        )

    def _set_pending_user_text(self, text: str) -> None:
        with self._pending_lock:
            self._pending_user_text = text

    def _pop_pending_user_text(self) -> Optional[str]:
        with self._pending_lock:
            text = self._pending_user_text
            self._pending_user_text = None
        return text

    def _drain_pending_user_text(self) -> None:
        pending = self._pop_pending_user_text()
        if not pending or not self._alive.is_set():
            return
        print(f"You: {pending}")
        self._start_reply(pending)

    def _handle_barge_in_frame(self, chunk: bytes) -> bool:
        if not self.cfg.barge_in_enabled or not chunk:
            return False
        if self._barge_in.is_set():
            return True

        try:
            level = audioop.rms(chunk, self.audio.WIDTH)
        except Exception:
            return False

        if level >= max(self.cfg.barge_in_rms_threshold, 1):
            self._barge_in_frames += 1
        else:
            self._barge_in_frames = 0

        if self._barge_in_frames < max(self.cfg.barge_in_frames_required, 1):
            return False
        self._barge_in_frames = 0
        return self._interrupt_current_reply()

    def _interrupt_current_reply(self) -> bool:
        with self._interrupt_lock:
            if self._barge_in.is_set():
                return True
            with self._reply_lock:
                cancel = self._cancel
            if cancel is None or cancel.is_set():
                return False
            print("[Barge-in detected]")
            cancel.set()
            self._barge_in.set()
            self.audio.interrupt()
            if self._stt is not None:
                self._stt.resume()
            self._set_state("listening")
            return True

    def _swap_cancel(self) -> threading.Event:
        cancel = threading.Event()
        with self._reply_lock:
            old, self._cancel = self._cancel, cancel
        if old is not None and not old.is_set():
            old.set()
        return cancel

    def _finish_cancel(self, cancel: threading.Event) -> None:
        with self._reply_lock:
            if self._cancel is cancel:
                self._cancel = None

    def _finish_activity(self, cancel: threading.Event) -> None:
        self._busy.clear()
        self._barge_in.clear()
        self._barge_in_frames = 0
        self.audio.clear_interrupt()
        if self._stt is not None:
            self._stt.resume()
        self._set_state("listening")
        self._finish_cancel(cancel)
        self._drain_pending_user_text()

    def _speak_async(self, text: str, language_code: str, *, save_turn: bool = False) -> None:
        cancel = self._swap_cancel()
        self._barge_in.clear()
        self._barge_in_frames = 0
        if save_turn:
            self.session.add_turn(role="assistant", content=text)

        def job() -> None:
            try:
                self.audio.clear_interrupt()
                self._busy.set()
                self._set_state("speaking")
                if self._stt is not None:
                    self._stt.pause()
                print(f"Agent ({_language_name(language_code)}): {text}")
                self._speak_chunked(text, language_code, cancel)
                self._wait_for_audio(cancel)
            finally:
                self._finish_activity(cancel)

        threading.Thread(target=job, daemon=True, name="tts").start()

    def _start_reply(self, user_text: str) -> None:
        cancel = self._swap_cancel()
        self._barge_in.clear()
        self._barge_in_frames = 0
        self.session.add_turn(role="user", content=user_text)
        self._last_language_code = _detect_language_code(
            user_text,
            last_language_code=self._last_language_code,
        )
        print(f"[lang {self._last_language_code}]")

        def job() -> None:
            try:
                self.audio.clear_interrupt()
                self._busy.set()
                self._set_state("thinking")
                if self._stt is not None:
                    self._stt.pause()
                self._run_reply(user_text, self._last_language_code, cancel)
            finally:
                self._finish_activity(cancel)

        threading.Thread(target=job, daemon=True, name="reply").start()

    def _build_messages(self, system: str, user_text: str) -> list:
        history = [item for item in self.session.get_history() if item.get("content")]
        prior = history[:-1] if history and history[-1].get("role") == "user" else history
        prior = prior[-4:]
        messages = [{"role": "system", "content": system}]
        calendar_context = self._calendar_context_message()
        if calendar_context:
            messages.append({"role": "system", "content": calendar_context})
        while prior and prior[0].get("role") != "user":
            prior = prior[1:]
        for turn in prior:
            role = "user" if turn.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": turn["content"]})
        if messages[-1]["role"] != "user" or messages[-1]["content"] != user_text:
            messages.append({"role": "user", "content": user_text})
        return messages

    def _calendar_context_message(self) -> str:
        with self._calendar_lock:
            event = dict(self._last_calendar_event) if self._last_calendar_event else None
        if not event:
            return ""
        summary = (event.get("summary") or "appointment").strip()
        event_id = (event.get("event_id") or "").strip()
        start_iso = (event.get("start_iso") or "").strip()
        end_iso = (event.get("end_iso") or "").strip()
        parts = [
            "RECENT CALENDAR CONTEXT:",
            f"title={summary}",
        ]
        if event_id:
            parts.append(f"event_id={event_id}")
        if start_iso:
            parts.append(f"start_iso={start_iso}")
        if end_iso:
            parts.append(f"end_iso={end_iso}")
        parts.append("Use this only when the user clearly refers to the same appointment.")
        return " ".join(parts)

    def _prepare_tool_call(self, call: ToolCall) -> ToolCall:
        if call.name not in {"update_calendar_event", "delete_calendar_event"}:
            return call

        args = dict(call.arguments or {})
        with self._calendar_lock:
            last = dict(self._last_calendar_event) if self._last_calendar_event else None
        if not last:
            return call

        if not args.get("title") and last.get("summary"):
            args["title"] = last["summary"]
        if not args.get("target_date") and last.get("start_iso"):
            args["target_date"] = str(last["start_iso"])[:10]

        if not args.get("event_id"):
            title_matches = _normalize_lookup_text(args.get("title")) == _normalize_lookup_text(last.get("summary"))
            if not call.arguments.get("title") or title_matches:
                args["event_id"] = last.get("event_id")

        return ToolCall(name=call.name, arguments=args, raw=call.raw)

    def _remember_calendar_result(self, tool_name: str, result_json: str) -> None:
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            return
        if not result.get("ok"):
            return

        if tool_name == "delete_calendar_event":
            with self._calendar_lock:
                self._last_calendar_event = None
            return

        event_id = (result.get("event_id") or "").strip()
        if not event_id:
            return
        with self._calendar_lock:
            self._last_calendar_event = {
                "event_id": event_id,
                "summary": result.get("summary") or "",
                "start_iso": _extract_event_iso(result.get("start")),
                "end_iso": _extract_event_iso(result.get("end")),
            }

    def _speak(self, text: str, language_code: str, cancel: threading.Event) -> bool:
        clean = (text or "").strip()
        if not clean or cancel.is_set():
            return True
        try:
            return bool(
                self.tts.synthesize(
                    text=clean,
                    language_code=language_code,
                    on_chunk=self.audio.play,
                    cancel_event=cancel,
                )
            )
        except Exception as exc:
            print(f"[TTS] {exc}")
            return False

    def _speak_chunked(self, text: str, language_code: str, cancel: threading.Event) -> bool:
        chunker = TextChunker()
        ok = False
        for part in chunker.feed(text):
            if cancel.is_set():
                return ok
            ok = self._speak(part, language_code, cancel) or ok
        for part in chunker.flush():
            if cancel.is_set():
                return ok
            ok = self._speak(part, language_code, cancel) or ok
        return ok

    def _run_tool(self, call: ToolCall) -> str:
        call = self._prepare_tool_call(call)
        print(f"[Tool: {call.name} {call.arguments}]")
        timeout = max(float(self.cfg.tool_timeout_seconds), 0.0)
        payload = json.dumps(call.arguments)

        def invoke() -> str:
            return dispatch_function(call.name, payload)

        try:
            future = self.pool.submit(invoke)
            raw = future.result(timeout=timeout) if timeout > 0 else future.result()
            print(f"[Tool result: {raw[:200]}]")
            self._remember_calendar_result(call.name, raw)
            return raw
        except concurrent.futures.TimeoutError:
            print(f"[Tool timeout {call.name}]")
            return json.dumps({"ok": False, "error": "The tool request timed out."})
        except Exception as exc:
            print(f"[Tool error: {exc}]")
            return json.dumps({"ok": False, "error": str(exc)})

    def _run_reply(self, user_text: str, language_code: str, cancel: threading.Event) -> None:
        system = build_system_prompt(user_language=_language_name(language_code))
        messages = self._build_messages(system, user_text)
        can_stream_audio = (
            language_code == DEFAULT_LANGUAGE_CODE
            and not _looks_like_calendar_request(user_text)
        )
        if can_stream_audio:
            self._run_streaming_reply(messages, language_code, cancel)
            return
        self._run_buffered_reply(messages, language_code, cancel)

    def _run_streaming_reply(
        self,
        messages: list,
        language_code: str,
        cancel: threading.Event,
    ) -> None:
        parser = ToolStreamParser()
        chunker = TextChunker()
        transcript_parts: List[str] = []
        spoken_parts: List[str] = []
        pending_tool: Optional[ToolCall] = None
        llm_failed = False
        spoke_any = False

        try:
            for event in self.llm.stream(
                messages,
                temperature=min(self.cfg.nebius_llm_temperature, 0.3),
                max_tokens=min(self.cfg.nebius_llm_max_tokens, 260),
            ):
                if cancel.is_set():
                    break
                if event.get("type") != "text":
                    continue
                content = event.get("content") or ""
                if not content:
                    continue
                transcript_parts.append(content)
                for piece in parser.feed(content):
                    if cancel.is_set():
                        break
                    if isinstance(piece, ToolCall):
                        if spoke_any or spoken_parts:
                            print("[Tool ignored after spoken text]")
                        else:
                            pending_tool = piece
                        break
                    text_piece = str(piece)
                    if not text_piece:
                        continue
                    spoken_parts.append(text_piece)
                    for chunk in chunker.feed(text_piece):
                        if cancel.is_set():
                            break
                        self._set_state("speaking")
                        if self._speak(chunk, language_code, cancel):
                            spoke_any = True
                if pending_tool is not None:
                    break
        except Exception as exc:
            print(f"[LLM] {exc}")
            llm_failed = True

        if llm_failed and not transcript_parts and not cancel.is_set():
            self._speak_llm_failure(language_code, cancel)
            return

        if pending_tool is not None and not cancel.is_set():
            self._speak_tool_result(pending_tool, language_code, cancel)
            self._wait_for_audio(cancel)
            return

        for piece in parser.flush():
            text_piece = str(piece)
            if not text_piece:
                continue
            spoken_parts.append(text_piece)
            for chunk in chunker.feed(text_piece):
                if cancel.is_set():
                    break
                self._set_state("speaking")
                if self._speak(chunk, language_code, cancel):
                    spoke_any = True

        for chunk in chunker.flush():
            if cancel.is_set():
                break
            self._set_state("speaking")
            if self._speak(chunk, language_code, cancel):
                spoke_any = True

        final = "".join(spoken_parts).strip()
        if final and not cancel.is_set():
            print(f"Agent ({_language_name(language_code)}): {final}")
            self.session.add_turn(role="assistant", content=final)
        elif llm_failed and not spoke_any and not cancel.is_set():
            self._speak_llm_failure(language_code, cancel)
            return

        self._wait_for_audio(cancel)

    def _run_buffered_reply(
        self,
        messages: list,
        language_code: str,
        cancel: threading.Event,
    ) -> None:
        parser = ToolStreamParser()
        transcript_parts: List[str] = []
        llm_failed = False

        try:
            for event in self.llm.stream(
                messages,
                temperature=min(self.cfg.nebius_llm_temperature, 0.3),
                max_tokens=min(self.cfg.nebius_llm_max_tokens, 260),
            ):
                if cancel.is_set():
                    break
                if event.get("type") != "text":
                    continue
                content = event.get("content") or ""
                if content:
                    transcript_parts.append(content)
        except Exception as exc:
            print(f"[LLM] {exc}")
            llm_failed = True

        if llm_failed and not transcript_parts and not cancel.is_set():
            self._speak_llm_failure(language_code, cancel)
            return

        pending_tool: Optional[ToolCall] = None
        text_parts: List[str] = []
        full_text = "".join(transcript_parts)
        for piece in parser.feed(full_text):
            if isinstance(piece, ToolCall):
                pending_tool = piece
                break
            text_parts.append(str(piece))
        if pending_tool is None:
            for piece in parser.flush():
                if isinstance(piece, ToolCall):
                    pending_tool = piece
                    break
                text_parts.append(str(piece))

        if pending_tool is not None and not cancel.is_set():
            self._speak_tool_result(pending_tool, language_code, cancel)
        elif not cancel.is_set():
            final = "".join(text_parts).strip()
            if final:
                final = self._normalize_reply_language(final, language_code)
                print(f"Agent ({_language_name(language_code)}): {final}")
                self.session.add_turn(role="assistant", content=final)
                self._set_state("speaking")
                self._speak_chunked(final, language_code, cancel)

        self._wait_for_audio(cancel)

    def _speak_tool_result(self, call: ToolCall, language_code: str, cancel: threading.Event) -> None:
        raw = self._run_tool(call)
        message = confirm(call.name, raw, language_code)
        print(f"Agent ({_language_name(language_code)}): {message}")
        self.session.add_turn(role="assistant", content=message)
        self._set_state("speaking")
        self._speak_chunked(message, language_code, cancel)

    def _speak_llm_failure(self, language_code: str, cancel: threading.Event) -> None:
        fallback = _pick_message(_LLM_FAILURE, language_code)
        print(f"Agent ({_language_name(language_code)}) [fallback]: {fallback}")
        self.session.add_turn(role="assistant", content=fallback)
        self._set_state("speaking")
        self._speak_chunked(fallback, language_code, cancel)
        self._wait_for_audio(cancel)

    def _normalize_reply_language(self, text: str, language_code: str) -> str:
        clean = (text or "").strip()
        if not clean or language_code != HINDI_LANGUAGE_CODE:
            return clean
        if _has_devanagari(clean) or not _looks_clearly_english(clean):
            return clean

        translated = self.llm.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Translate the assistant reply into natural Hindi for speech. "
                        "Keep the meaning the same. Output only the Hindi translation."
                    ),
                },
                {"role": "user", "content": clean},
            ],
            temperature=0.0,
            max_tokens=min(self.cfg.nebius_llm_max_tokens, 260),
        ).strip()
        if translated:
            return translated
        return clean

    def _wait_for_audio(self, cancel: threading.Event) -> None:
        self.audio.flush_playback_tail()
        quiet = 0
        while not cancel.is_set():
            if self.audio.is_playing():
                quiet = 0
            else:
                quiet += 1
                if quiet >= 4:
                    return
            time.sleep(0.05)


def _pick_message(table: dict[str, str], language_code: str) -> str:
    return table.get(language_code) or table[DEFAULT_LANGUAGE_CODE]


def _language_name(language_code: str) -> str:
    return _LANGUAGE_NAMES.get(language_code, _LANGUAGE_NAMES[DEFAULT_LANGUAGE_CODE])


def _detect_language_code(text: str, *, last_language_code: str = DEFAULT_LANGUAGE_CODE) -> str:
    clean = (text or "").strip()
    if not clean:
        return last_language_code or DEFAULT_LANGUAGE_CODE
    if _has_devanagari(clean) or _looks_like_hinglish(clean):
        return HINDI_LANGUAGE_CODE
    if _looks_clearly_english(clean):
        return DEFAULT_LANGUAGE_CODE
    if last_language_code == HINDI_LANGUAGE_CODE:
        return HINDI_LANGUAGE_CODE
    return DEFAULT_LANGUAGE_CODE


def _has_devanagari(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if 0x0900 <= code <= 0x097F:
            return True
    return False


def _looks_like_hinglish(text: str) -> bool:
    words = _alpha_words(text)
    if not words:
        return False
    hits = sum(1 for word in words if word in _HINDI_HINTS)
    if hits >= 2:
        return True
    if hits >= 1 and len(words) <= 4:
        return True
    return False


def _looks_clearly_english(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    ascii_ratio = sum(1 for ch in letters if ch.isascii()) / len(letters)
    if ascii_ratio < 0.98:
        return False
    words = _alpha_words(text)
    if len(words) < 2:
        return False
    hits = sum(1 for word in words if word in _ENGLISH_HINTS)
    return hits >= 1


def _alpha_words(text: str) -> list[str]:
    words: list[str] = []
    for raw in text.split():
        token = "".join(ch for ch in raw.lower() if ch.isalpha())
        if token:
            words.append(token)
    return words


def _looks_like_calendar_request(text: str) -> bool:
    clean = (text or "").strip().lower()
    if not clean:
        return False
    words = set(_alpha_words(clean))
    if words.intersection(_CALENDAR_HINTS):
        return True
    return any(token in clean for token in _CALENDAR_HINTS if any(ord(ch) > 127 for ch in token))


def _extract_event_iso(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("dateTime") or "").strip()


def _normalize_lookup_text(value: object) -> str:
    if not value:
        return ""
    text = "".join(ch for ch in str(value).casefold() if ch.isalnum())
    return text
