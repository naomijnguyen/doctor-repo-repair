import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .api import handle_request
from .config import get_port
from .repository import NoteRepository
from .service import NoteService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fieldnotes")

repository = NoteRepository()
service = NoteService(repository)


class Handler(BaseHTTPRequestHandler):
    def _handle(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        status, headers, response = handle_request(self.command, self.path, body, service)
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if response:
            self.wfile.write(response)

    do_GET = _handle
    do_POST = _handle
    do_DELETE = _handle

    def log_message(self, fmt, *args):
        logger.info(fmt, *args)


def main():
    port = get_port()
    logger.info("Field Notes listening on http://127.0.0.1:%s", port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
