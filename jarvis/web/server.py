"""HTTP transport: routing, JSON and static files. Built on the standard
library, so there is nothing to install. For heavy traffic, replace this one
file with FastAPI or Flask routes that call the same `Api` methods."""
from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from ..app import Container
from ..errors import InvalidInputError, JarvisError, LLMUnavailableError
from .api import Api

log = logging.getLogger("jarvis.web")

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY_BYTES = 64 * 1024
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

Handler = Callable[[dict[str, Any]], dict[str, Any]]


def _make_handler(api: Api) -> type[BaseHTTPRequestHandler]:
    get_routes: dict[str, Handler] = {
        "/api/health": api.health,
        "/api/chats": api.chats,
        "/api/history": api.history,
        "/api/cheats": api.cheats,
    }
    post_routes: dict[str, Handler] = {
        "/api/chat": api.chat,
        "/api/classify": api.classify,
    }

    class JarvisHandler(BaseHTTPRequestHandler):
        server_version = "Jarvis/1.0"

        def do_GET(self) -> None:  # noqa: N802 (name required by http.server)
            url = urlparse(self.path)
            route = get_routes.get(url.path)
            if route:
                query = {k: v[0] for k, v in parse_qs(url.query).items()}
                self._run(route, query)
            else:
                self._send_static(url.path)

        def do_POST(self) -> None:  # noqa: N802
            route = post_routes.get(urlparse(self.path).path)
            if not route:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
                return
            try:
                body = self._read_json()
            except InvalidInputError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._run(route, body)

        # -- helpers -------------------------------------------------------------

        def _run(self, route: Handler, payload: dict[str, Any]) -> None:
            try:
                self._send_json(HTTPStatus.OK, route(payload))
            except InvalidInputError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except LLMUnavailableError as exc:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
            except JarvisError as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": str(exc)})
            except Exception:  # last line of defence: never crash the server
                log.exception("Unexpected error")
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "Something went wrong inside Jarvis. Check the terminal."},
                )

        def _read_json(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError as exc:
                raise InvalidInputError("Bad Content-Length.") from exc
            if length > MAX_BODY_BYTES:
                raise InvalidInputError("Request is too large.")
            if not length:
                return {}
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise InvalidInputError("Request body is not valid JSON.") from exc
            if not isinstance(data, dict):
                raise InvalidInputError("Request body must be a JSON object.")
            return data

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, path: str) -> None:
            relative = "index.html" if path in ("", "/") else path.lstrip("/")
            target = (STATIC_DIR / relative).resolve()
            inside = STATIC_DIR.resolve() in target.parents
            if not inside or not target.is_file() or target.suffix not in CONTENT_TYPES:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
                return
            body = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", CONTENT_TYPES[target.suffix])
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            log.debug("%s - %s", self.address_string(), format % args)

    return JarvisHandler


def create_server(container: Container, host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    address = (host or container.settings.host, container.settings.port if port is None else port)
    server = ThreadingHTTPServer(address, _make_handler(Api(container)))
    server.daemon_threads = True
    return server


def serve(container: Container) -> None:
    server = create_server(container)
    host, port = server.server_address[:2]
    print(f"\n  JARVIS is online  ->  http://{host}:{port}")
    print(f"  Model: {container.settings.model}   (Ctrl+C to stop)\n")
    if not container.llm.is_available():
        print("  ! Ollama is not reachable yet. Open the Ollama app or run: ollama serve\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Jarvis is offline. Bye.")
    finally:
        server.server_close()
