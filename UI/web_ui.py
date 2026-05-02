from __future__ import annotations

import mimetypes
import queue
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from UI.event_bus import UIEventBus


_STATIC_DIR = Path(__file__).resolve().parent / "static"


class _VoiceUIHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_cls, *, event_bus: UIEventBus, static_dir: Path):
        super().__init__(server_address, handler_cls)
        self.event_bus = event_bus
        self.static_dir = static_dir.resolve()


class _VoiceUIHandler(BaseHTTPRequestHandler):
    server_version = "VoiceUI/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/events":
            self._serve_events()
            return
        self._serve_static(path)

    def log_message(self, fmt: str, *args) -> None:
        return

    def _serve_events(self) -> None:
        bus = self.server.event_bus
        subscriber_id, q, snapshot = bus.subscribe()
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            for payload in snapshot:
                self._write_sse(payload)

            while True:
                try:
                    payload = q.get(timeout=15.0)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                self._write_sse(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            bus.unsubscribe(subscriber_id)

    def _write_sse(self, payload: str) -> None:
        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _serve_static(self, path: str) -> None:
        rel = "index.html" if path in ("", "/") else unquote(path.lstrip("/"))
        target = (self.server.static_dir / rel).resolve()
        if not str(target).startswith(str(self.server.static_dir)) or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        mime, _ = mimetypes.guess_type(str(target))
        mime = mime or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") else mime)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class VoiceUIWebServer:
    def __init__(
        self,
        event_bus: UIEventBus,
        *,
        host: str = "127.0.0.1",
        preferred_port: int = 8765,
        static_dir: Path = _STATIC_DIR,
    ):
        self._event_bus = event_bus
        self._host = host
        self._preferred_port = preferred_port
        self._static_dir = static_dir
        self._httpd: Optional[_VoiceUIHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._url: Optional[str] = None

    @property
    def url(self) -> str:
        return self._url or "unavailable"

    def start(self) -> None:
        if self._httpd is not None:
            return

        last_exc: Optional[Exception] = None
        for port in range(self._preferred_port, self._preferred_port + 20):
            try:
                self._httpd = _VoiceUIHTTPServer(
                    (self._host, port),
                    _VoiceUIHandler,
                    event_bus=self._event_bus,
                    static_dir=self._static_dir,
                )
                self._url = f"http://{self._host}:{port}/"
                break
            except OSError as exc:
                last_exc = exc

        if self._httpd is None:
            raise RuntimeError(f"Unable to start Voice UI server: {last_exc}")

        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            kwargs={"poll_interval": 0.2},
            daemon=True,
            name="voice-ui-http",
        )
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._httpd = None
        self._thread = None


def _run_demo() -> None:
    bus = UIEventBus()
    server = VoiceUIWebServer(bus)
    server.start()
    print(f"Voice UI demo: {server.url}")

    stop = threading.Event()

    def cycle() -> None:
        script = [
            ("connecting", None),
            ("speaking", ("agent", "Hey, I am online. Ask me anything.")),
            ("listening", None),
            ("listening", ("user", "When is my next meeting?")),
            ("thinking", None),
            ("speaking", ("agent", "Your next meeting is at 3 PM today.")),
            ("listening", None),
        ]
        idx = 0
        while not stop.is_set():
            state, line = script[idx % len(script)]
            bus.publish_state(state)
            if line is not None:
                role, text = line
                bus.publish_transcript(role, text)
            idx += 1
            time.sleep(2.2)

    thread = threading.Thread(target=cycle, daemon=True, name="voice-ui-demo")
    thread.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.stop()


if __name__ == "__main__":
    _run_demo()
