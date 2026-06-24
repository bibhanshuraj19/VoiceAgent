from __future__ import annotations

import audioop
import concurrent.futures
import json
import threading
import time
from typing import List, Optional

import pyaudio

from AGENT.agent_config import AgentConfig
from AGENT import language as lang
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


class VoiceAgent:
    """Deepgram STT + Nebius LLM + ElevenLabs TTS + calendar + optional web UI."""

    def __init__(self):
        self.cfg = AgentConfig()
        self.audio = AudioManager()
        self.session = SessionManager(max_history=30)
        self.session.set_on_turn(self._on_session_turn)

        self.ui_bus = UIEventBus() if self.cfg.voice_ui_enabled else None
        self.ui_server = (
            VoiceUIWebServer(self.ui_bus, host=self.cfg.voice_ui_host, preferred_port=self.cfg.voice_ui_port)
            if self.ui_bus
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
        self._last_lang = lang.EN
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
        if self.ui_server:
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
            if self.ui_server:
                self.ui_server.stop()
            raise
        self._stt.resume()
        self._set_state("listening")
        print("Ready.\n")
        self._speak_async(GREETING, lang.EN, save_turn=True)

        def on_mic(in_data, *_):
            if not self._alive.is_set():
                return (None, pyaudio.paContinue)
            if self._busy.is_set():
                if self._handle_barge_in_frame(in_data) and self._stt:
                    self._stt.feed(in_data)
            elif self._stt:
                self._stt.feed(in_data)
            return (None, pyaudio.paContinue)

        self.audio.open_mic(on_mic)
        try:
            while self._alive.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\nStop.")
        finally:
            self._shutdown()

    def _shutdown(self):
        self._alive.clear()
        self._clear_timer()
        if self._stt:
            self._stt.close()
        self.audio.close()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.tts.close()
        if self.ui_server:
            self.ui_server.stop()
        self.session.save()

    def _set_state(self, state: str) -> None:
        with self._state_lock:
            self._state = state
        if self.ui_bus:
            self.ui_bus.publish_state({"booting": "connecting", "connecting": "connecting"}.get(state, state))

    def _on_session_turn(self, turn: dict) -> None:
        if not self.ui_bus:
            return
        role = (turn.get("role") or "").strip().lower()
        text = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and text:
            self.ui_bus.publish_transcript("user" if role == "user" else "agent", text)

    def _arm_timer(self) -> None:
        seconds = max(float(self.cfg.no_transcript_nudge_seconds), 0.0)
        if seconds <= 0:
            return
        with self._timer_lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(seconds, self._on_no_transcript)
            self._timer.daemon = True
            self._timer.start()

    def _clear_timer(self) -> None:
        with self._timer_lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None

    def _on_no_transcript(self) -> None:
        if self._alive.is_set() and not self._busy.is_set():
            print("[No transcript]")
            self._speak_async(lang.pick(lang.DID_NOT_CATCH, self._last_lang), self._last_lang)

    def _set_pending_user_text(self, text: str) -> None:
        with self._pending_lock:
            self._pending_user_text = text

    def _pop_pending_user_text(self) -> Optional[str]:
        with self._pending_lock:
            text, self._pending_user_text = self._pending_user_text, None
        return text

    def _drain_pending_user_text(self) -> None:
        if pending := self._pop_pending_user_text():
            if self._alive.is_set():
                print(f"You: {pending}")
                self._start_reply(pending)

    def _handle_barge_in_frame(self, chunk: bytes) -> bool:
        if not self.cfg.barge_in_enabled or not chunk or self._barge_in.is_set():
            return bool(self._barge_in.is_set())
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
            if not cancel or cancel.is_set():
                return False
            print("[Barge-in detected]")
            cancel.set()
            self._barge_in.set()
            self.audio.interrupt()
            if self._stt:
                self._stt.resume()
            self._set_state("listening")
            return True

    def _swap_cancel(self) -> threading.Event:
        cancel = threading.Event()
        with self._reply_lock:
            old, self._cancel = self._cancel, cancel
        if old and not old.is_set():
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
        if self._stt:
            self._stt.resume()
        self._set_state("listening")
        self._finish_cancel(cancel)
        self._drain_pending_user_text()

    def _spawn(self, name: str, fn) -> None:
        threading.Thread(target=fn, daemon=True, name=name).start()

    def _speak_async(self, text: str, language_code: str, *, save_turn: bool = False) -> None:
        cancel = self._swap_cancel()
        self._barge_in.clear()
        self._barge_in_frames = 0
        if save_turn:
            self.session.add_turn(role="assistant", content=text)

        def job():
            try:
                self.audio.clear_interrupt()
                self._busy.set()
                self._set_state("speaking")
                if self._stt:
                    self._stt.pause()
                print(f"Agent ({lang.name(language_code)}): {text}")
                self._speak_chunked(text, language_code, cancel)
                self._wait_for_audio(cancel)
            finally:
                self._finish_activity(cancel)

        self._spawn("tts", job)

    def _start_reply(self, user_text: str) -> None:
        cancel = self._swap_cancel()
        self._barge_in.clear()
        self._barge_in_frames = 0
        self.session.add_turn(role="user", content=user_text)
        self._last_lang = lang.detect(user_text, last=self._last_lang)
        print(f"[lang {self._last_lang}]")

        def job():
            try:
                self.audio.clear_interrupt()
                self._busy.set()
                self._set_state("thinking")
                if self._stt:
                    self._stt.pause()
                self._run_reply(user_text, self._last_lang, cancel)
            finally:
                self._finish_activity(cancel)

        self._spawn("reply", job)

    def _build_messages(self, system: str, user_text: str) -> list:
        history = [t for t in self.session.get_history() if t.get("content")]
        prior = history[:-1] if history and history[-1].get("role") == "user" else history
        prior = prior[-4:]
        messages = [{"role": "system", "content": system}]
        if ctx := self._calendar_context_message():
            messages.append({"role": "system", "content": ctx})
        while prior and prior[0].get("role") != "user":
            prior = prior[1:]
        for turn in prior:
            messages.append({"role": "user" if turn.get("role") == "user" else "assistant", "content": turn["content"]})
        if not messages or messages[-1].get("content") != user_text or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": user_text})
        return messages

    def _calendar_context_message(self) -> str:
        with self._calendar_lock:
            event = dict(self._last_calendar_event) if self._last_calendar_event else None
        if not event:
            return ""
        parts = ["RECENT CALENDAR CONTEXT:", f"title={event.get('summary') or 'appointment'}"]
        for key in ("event_id", "start_iso", "end_iso"):
            if val := (event.get(key) or "").strip():
                parts.append(f"{key}={val}")
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
            title = "".join(c for c in str(args.get("title") or "").casefold() if c.isalnum())
            summary = "".join(c for c in str(last.get("summary") or "").casefold() if c.isalnum())
            if not call.arguments.get("title") or title == summary:
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
        if event_id := (result.get("event_id") or "").strip():
            start = result.get("start") or {}
            end = result.get("end") or {}
            with self._calendar_lock:
                self._last_calendar_event = {
                    "event_id": event_id,
                    "summary": result.get("summary") or "",
                    "start_iso": str(start.get("dateTime") or "").strip() if isinstance(start, dict) else "",
                    "end_iso": str(end.get("dateTime") or "").strip() if isinstance(end, dict) else "",
                }

    def _speak(self, text: str, language_code: str, cancel: threading.Event) -> bool:
        clean = (text or "").strip()
        if not clean or cancel.is_set():
            return True
        try:
            return bool(
                self.tts.synthesize(text=clean, language_code=language_code, on_chunk=self.audio.play, cancel_event=cancel)
            )
        except Exception as exc:
            print(f"[TTS] {exc}")
            return False

    def _speak_chunked(self, text: str, language_code: str, cancel: threading.Event) -> bool:
        chunker = TextChunker()
        ok = False
        for part in list(chunker.feed(text)) + chunker.flush():
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

    def _llm_stream(self, messages: list):
        return self.llm.stream(
            messages,
            temperature=min(self.cfg.nebius_llm_temperature, 0.3),
            max_tokens=min(self.cfg.nebius_llm_max_tokens, 260),
        )

    def _run_reply(self, user_text: str, language_code: str, cancel: threading.Event) -> None:
        messages = self._build_messages(build_system_prompt(user_language=lang.name(language_code)), user_text)
        stream_tts = language_code == lang.EN and not lang.calendar_request(user_text)
        self._process_llm(messages, language_code, cancel, stream_tts=stream_tts)

    def _process_llm(self, messages: list, language_code: str, cancel: threading.Event, *, stream_tts: bool) -> None:
        parser = ToolStreamParser()
        chunker = TextChunker()
        transcript: List[str] = []
        spoken: List[str] = []
        pending_tool: Optional[ToolCall] = None
        llm_failed = spoke_any = False

        def consume(pieces) -> bool:
            nonlocal pending_tool, spoke_any
            for piece in pieces:
                if cancel.is_set():
                    return True
                if isinstance(piece, ToolCall):
                    if stream_tts and (spoke_any or spoken):
                        print("[Tool ignored after spoken text]")
                    else:
                        pending_tool = piece
                    return True
                text = str(piece)
                if not text:
                    continue
                spoken.append(text)
                if stream_tts:
                    for chunk in chunker.feed(text):
                        if cancel.is_set():
                            return True
                        self._set_state("speaking")
                        if self._speak(chunk, language_code, cancel):
                            spoke_any = True
            return False

        try:
            for event in self._llm_stream(messages):
                if cancel.is_set():
                    break
                if event.get("type") != "text":
                    continue
                content = event.get("content") or ""
                if not content:
                    continue
                transcript.append(content)
                if consume(parser.feed(content)) or pending_tool:
                    break
        except Exception as exc:
            print(f"[LLM] {exc}")
            llm_failed = True

        if llm_failed and not transcript and not cancel.is_set():
            self._speak_llm_failure(language_code, cancel)
            return

        if pending_tool and not cancel.is_set():
            self._speak_tool_result(pending_tool, language_code, cancel)
            self._wait_for_audio(cancel)
            return

        if consume(parser.flush()):
            if pending_tool and not cancel.is_set():
                self._speak_tool_result(pending_tool, language_code, cancel)
                self._wait_for_audio(cancel)
                return

        if stream_tts:
            for chunk in chunker.flush():
                if cancel.is_set():
                    break
                self._set_state("speaking")
                if self._speak(chunk, language_code, cancel):
                    spoke_any = True

        final = "".join(spoken).strip()
        if final and not cancel.is_set():
            if not stream_tts:
                final = self._normalize_reply_language(final, language_code)
            print(f"Agent ({lang.name(language_code)}): {final}")
            self.session.add_turn(role="assistant", content=final)
            if not stream_tts:
                self._set_state("speaking")
                self._speak_chunked(final, language_code, cancel)
        elif llm_failed and not spoke_any and not cancel.is_set():
            self._speak_llm_failure(language_code, cancel)
            return

        self._wait_for_audio(cancel)

    def _speak_tool_result(self, call: ToolCall, language_code: str, cancel: threading.Event) -> None:
        message = confirm(call.name, self._run_tool(call), language_code)
        print(f"Agent ({lang.name(language_code)}): {message}")
        self.session.add_turn(role="assistant", content=message)
        self._set_state("speaking")
        self._speak_chunked(message, language_code, cancel)

    def _speak_llm_failure(self, language_code: str, cancel: threading.Event) -> None:
        fallback = lang.pick(lang.LLM_FAILURE, language_code)
        print(f"Agent ({lang.name(language_code)}) [fallback]: {fallback}")
        self.session.add_turn(role="assistant", content=fallback)
        self._set_state("speaking")
        self._speak_chunked(fallback, language_code, cancel)
        self._wait_for_audio(cancel)

    def _normalize_reply_language(self, text: str, language_code: str) -> str:
        clean = (text or "").strip()
        if not clean or language_code != lang.HI:
            return clean
        if lang.has_devanagari(clean) or not lang.looks_english(clean):
            return clean
        translated = self.llm.complete(
            [
                {
                    "role": "system",
                    "content": "Translate the assistant reply into natural Hindi for speech. Keep the meaning the same. Output only the Hindi translation.",
                },
                {"role": "user", "content": clean},
            ],
            temperature=0.0,
            max_tokens=min(self.cfg.nebius_llm_max_tokens, 260),
        ).strip()
        return translated or clean

    def _wait_for_audio(self, cancel: threading.Event) -> None:
        self.audio.flush_playback_tail()
        quiet = 0
        while not cancel.is_set():
            if self.audio.is_playing():
                quiet = 0
            elif (quiet := quiet + 1) >= 4:
                return
            time.sleep(0.05)
