from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer


def make_health_handler(version: str) -> type[BaseHTTPRequestHandler]:
    payload = {"status": "ok", "version": version}
    body = json.dumps(payload).encode("utf-8")

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return HealthHandler


def serve_health(host: str, port: int, version: str) -> None:
    handler = make_health_handler(version)
    server = HTTPServer((host, port), handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
