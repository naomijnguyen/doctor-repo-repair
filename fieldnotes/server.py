from __future__ import annotations

import logging
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .api import handle_request
from .composition import create_service
from .config import get_port
from .service import NoteService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fieldnotes")

MAX_BODY_BYTES = 1_000_000
WEB_ROOT = Path(__file__).resolve().parents[1] / "web"


def is_allowed_origin(origin, host=None):
    if not origin:
        return False
    parsed = urlparse(origin)
    try:
        port = parsed.port
    except ValueError:
        return False
    allowed = (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and parsed.path in {"", "/"}
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
        and port is not None
    )
    if not allowed:
        return False
    return host is None or parsed.netloc.lower() == host.lower()

class Handler(SimpleHTTPRequestHandler):
    service: NoteService

    def _cors_origin(self):
        origin = self.headers.get("Origin")
        return origin if is_allowed_origin(origin, self.headers.get("Host", "")) else None

    def _send_error(self, status, code, message):
        response = (
            '{"error":{"code":"%s","message":"%s"}}' % (code, message)
        ).encode()
        self._send(status, {"Content-Type": "application/json"}, response)

    def _mutation_origin_is_allowed(self):
        origin = self.headers.get("Origin")
        return origin is None or is_allowed_origin(
            origin, self.headers.get("Host", "")
        )

    def _send(self, status, headers=None, response=b""):
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        if response:
            self.wfile.write(response)

    def _handle(self):
        parsed_path = urlparse(self.path).path
        if self.command in {"POST", "PUT", "PATCH", "DELETE"}:
            if not self._mutation_origin_is_allowed():
                self._send_error(403, "origin_not_allowed", "origin not allowed")
                return
        if self.command == "POST" and parsed_path in {"/api/notes", "/api/import"}:
            media_type = self.headers.get("Content-Type", "").split(";", 1)[0]
            if media_type.strip().lower() != "application/json":
                self._send_error(
                    415,
                    "unsupported_media_type",
                    "Content-Type must be application/json",
                )
                return

        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            self._send(400, {"Content-Type": "application/json"}, b'{"error":{"code":"invalid_content_length","message":"invalid Content-Length"}}')
            return
        if length < 0:
            self._send(400, {"Content-Type": "application/json"}, b'{"error":{"code":"invalid_content_length","message":"invalid Content-Length"}}')
            return
        if length > MAX_BODY_BYTES:
            self._send(413, {"Content-Type": "application/json"}, b'{"error":{"code":"request_too_large","message":"request body is too large"}}')
            return
        body = self.rfile.read(length) if length else b""
        try:
            status, headers, response = handle_request(
                self.command, self.path, body, self.service
            )
        except Exception:
            logger.exception("Unhandled request error")
            status = 500
            headers = {"Content-Type": "application/json"}
            response = b'{"error":{"code":"internal_error","message":"internal server error"}}'
        self._send(status, headers, response)

    def do_OPTIONS(self):
        origin = self._cors_origin()
        if not origin:
            self._send(403, {"Content-Type": "application/json"}, b'{"error":{"code":"origin_not_allowed","message":"origin not allowed"}}')
            return
        self._send(204, {
            "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    def do_GET(self):
        if urlparse(self.path).path.startswith("/api/"):
            self._handle()
            return
        super().do_GET()

    do_POST = _handle
    do_DELETE = _handle
    do_PATCH = _handle
    do_PUT = _handle

    def log_message(self, fmt, *args):
        logger.info(fmt, *args)


def handler_for(service: NoteService):
    """Bind one composed service to all handlers created by an HTTP server."""

    class ServiceHandler(Handler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    ServiceHandler.service = service
    return ServiceHandler


def build_server(port: int | None = None, data_path=None):
    """Build a configured server and return its repository lifecycle owner."""
    selected_port = get_port() if port is None else port
    service, repository = create_service(data_path)
    try:
        server = ThreadingHTTPServer(
            ("127.0.0.1", selected_port), handler_for(service)
        )
    except Exception:
        repository.close()
        raise
    return server, repository


def main():
    server, repository = build_server()
    port = server.server_address[1]
    logger.info("Field Notes UI and API listening on http://127.0.0.1:%s", port)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        repository.close()


if __name__ == "__main__":
    main()
